from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflicto, no_encontrado, no_procesable
from app.core.security import Usuario
from app.db import models
from app.schemas.liquidaciones import (
    EstadoLiquidacion,
    Liquidacion,
    LiquidacionCreate,
    Saldo,
    TransferenciaConfirmacion,
)
from app.schemas.movimientos import TipoMovimiento
from app.services import movimientos
from app.services.pagos import ESTADOS_COBRADOS

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")

_COBRADOS = [e.value for e in ESTADOS_COBRADOS]

TRANSICIONES = {
    EstadoLiquidacion.pendiente: {EstadoLiquidacion.transferida, EstadoLiquidacion.anulada},
    EstadoLiquidacion.transferida: set(),
    EstadoLiquidacion.anulada: set(),
}


@dataclass(frozen=True)
class Montos:
    bruto: Decimal
    comision: Decimal
    neto: Decimal


# --- Reglas puras -----------------------------------------------------------


def neto_pago(monto_capturado: Decimal, monto_reembolsado: Decimal) -> Decimal:
    return monto_capturado - monto_reembolsado


def calcular_montos(netos: list[Decimal], porcentaje_comision: Decimal) -> Montos:
    bruto = sum(netos, CERO)
    comision = (bruto * porcentaje_comision).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return Montos(bruto=bruto, comision=comision, neto=bruto - comision)


def calcular_saldo(
    beneficiario_id: UUID, netos_sin_liquidar: list[Decimal], liquidaciones: list[tuple[EstadoLiquidacion, Decimal]]
) -> Saldo:
    def total(estado: EstadoLiquidacion) -> Decimal:
        return sum((neto for e, neto in liquidaciones if e == estado), CERO)

    return Saldo(
        beneficiario_id=beneficiario_id,
        saldo_pendiente_liquidar=sum(netos_sin_liquidar, CERO),
        liquidado_pendiente_transferir=total(EstadoLiquidacion.pendiente),
        total_transferido=total(EstadoLiquidacion.transferida),
    )


def validar_transicion(actual: EstadoLiquidacion, nuevo: EstadoLiquidacion) -> None:
    if nuevo not in TRANSICIONES[actual]:
        raise conflicto(
            "transicion-invalida",
            "El estado de la liquidación no admite la operación",
            f"La liquidación ya está en estado '{actual.value}'",
        )


# --- Acceso a datos ---------------------------------------------------------


def _consulta_liquidables(beneficiario_id: UUID):
    """Pagos cobrados del beneficiario que todavía no están en una liquidación vigente."""
    return select(models.Pago).where(
        models.Pago.beneficiario_id == beneficiario_id,
        models.Pago.estado.in_(_COBRADOS),
        models.Pago.liquidacion_id.is_(None),
    )


def generar_liquidacion(db: Session, datos: LiquidacionCreate, usuario: Usuario) -> Liquidacion:
    desde = datetime.combine(datos.periodo_desde, time.min, tzinfo=timezone.utc)
    hasta = datetime.combine(datos.periodo_hasta + timedelta(days=1), time.min, tzinfo=timezone.utc)
    # FOR UPDATE: dos liquidaciones simultáneas no pueden tomar el mismo pago
    pagos = db.scalars(
        _consulta_liquidables(datos.beneficiario_id)
        .where(models.Pago.capturado_en >= desde, models.Pago.capturado_en < hasta)
        .order_by(models.Pago.creado_en)
        .with_for_update()
    ).all()
    netos = [neto_pago(p.monto_capturado, p.monto_reembolsado) for p in pagos]
    if not pagos or sum(netos, CERO) <= 0:
        raise no_procesable("sin-pagos-para-liquidar", "No hay pagos pendientes de liquidar en el período indicado")
    porcentaje = settings.comision_plataforma
    montos = calcular_montos(netos, porcentaje)
    ahora = datetime.now(timezone.utc)
    liquidacion = models.Liquidacion(
        id=uuid4(),
        beneficiario_id=datos.beneficiario_id,
        periodo_desde=datos.periodo_desde,
        periodo_hasta=datos.periodo_hasta,
        monto_bruto=montos.bruto,
        comision_porcentaje=porcentaje,
        comision_plataforma=montos.comision,
        monto_neto=montos.neto,
        moneda="ARS",
        estado=EstadoLiquidacion.pendiente.value,
        creada_en=ahora,
        actualizada_en=ahora,
        pagos=list(pagos),
    )
    db.add(liquidacion)
    db.flush()
    for pago in pagos:
        pago.liquidacion_id = liquidacion.id
    movimientos.registrar(
        db,
        TipoMovimiento.liquidacion_generada,
        usuario.sub,
        montos.neto,
        liquidacion=liquidacion,
        detalle=f"Bruto {montos.bruto}, comisión {montos.comision} ({porcentaje})",
    )
    db.commit()
    return Liquidacion.model_validate(liquidacion)


def buscar(db: Session, liquidacion_id: UUID, bloquear: bool = False) -> models.Liquidacion:
    consulta = select(models.Liquidacion).where(models.Liquidacion.id == liquidacion_id)
    if bloquear:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    liquidacion = db.scalar(consulta)
    if liquidacion is None:
        raise no_encontrado("Liquidación no encontrada")
    return liquidacion


def obtener_liquidacion(db: Session, liquidacion_id: UUID) -> Liquidacion:
    return Liquidacion.model_validate(buscar(db, liquidacion_id))


def listar_liquidaciones(
    db: Session, beneficiario_id: UUID | None, estado: EstadoLiquidacion | None
) -> list[Liquidacion]:
    consulta = select(models.Liquidacion).order_by(models.Liquidacion.creada_en)
    if beneficiario_id is not None:
        consulta = consulta.where(models.Liquidacion.beneficiario_id == beneficiario_id)
    if estado is not None:
        consulta = consulta.where(models.Liquidacion.estado == estado.value)
    return [Liquidacion.model_validate(liq) for liq in db.scalars(consulta)]


def _cambiar_estado(db: Session, liquidacion_id: UUID, nuevo: EstadoLiquidacion) -> models.Liquidacion:
    liquidacion = buscar(db, liquidacion_id, bloquear=True)
    validar_transicion(EstadoLiquidacion(liquidacion.estado), nuevo)
    liquidacion.estado = nuevo.value
    liquidacion.actualizada_en = datetime.now(timezone.utc)
    return liquidacion


def confirmar_transferencia(
    db: Session, liquidacion_id: UUID, datos: TransferenciaConfirmacion, usuario: Usuario
) -> Liquidacion:
    liquidacion = _cambiar_estado(db, liquidacion_id, EstadoLiquidacion.transferida)
    liquidacion.referencia_transferencia = datos.referencia_transferencia
    movimientos.registrar(
        db,
        TipoMovimiento.liquidacion_transferida,
        usuario.sub,
        liquidacion.monto_neto,
        liquidacion=liquidacion,
        referencia=datos.referencia_transferencia,
    )
    db.commit()
    return Liquidacion.model_validate(liquidacion)


def anular(db: Session, liquidacion_id: UUID, usuario: Usuario) -> Liquidacion:
    """Anula la liquidación y libera sus pagos para una nueva liquidación."""
    liquidacion = _cambiar_estado(db, liquidacion_id, EstadoLiquidacion.anulada)
    for pago in liquidacion.pagos:
        pago.liquidacion_id = None
    movimientos.registrar(
        db, TipoMovimiento.liquidacion_anulada, usuario.sub, liquidacion.monto_neto, liquidacion=liquidacion
    )
    db.commit()
    return Liquidacion.model_validate(liquidacion)


def obtener_saldo(db: Session, beneficiario_id: UUID) -> Saldo:
    pagos = db.scalars(_consulta_liquidables(beneficiario_id)).all()
    liquidaciones = db.execute(
        select(models.Liquidacion.estado, models.Liquidacion.monto_neto).where(
            models.Liquidacion.beneficiario_id == beneficiario_id
        )
    ).all()
    return calcular_saldo(
        beneficiario_id,
        [neto_pago(p.monto_capturado, p.monto_reembolsado) for p in pagos],
        [(EstadoLiquidacion(estado), neto) for estado, neto in liquidaciones],
    )
