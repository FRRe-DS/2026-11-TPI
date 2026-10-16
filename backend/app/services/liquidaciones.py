from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.liquidaciones import (
    EstadoLiquidacion,
    Liquidacion,
    LiquidacionCreate,
    Saldo,
    TransferenciaConfirmacion,
)
from app.schemas.pagos import Pago
from app.services import store
from app.services.pagos import ESTADOS_COBRADOS

# TODO: definir con la cátedra/negocio el porcentaje real de comisión
COMISION_PLATAFORMA = Decimal("0.20")
CENTAVOS = Decimal("0.01")


def _pagos_ya_liquidados() -> set[UUID]:
    return {
        pago_id
        for liq in store.liquidaciones.values()
        if liq.estado != EstadoLiquidacion.anulada
        for pago_id in liq.pago_ids
    }


def _pagos_liquidables(beneficiario_id: UUID) -> list[Pago]:
    liquidados = _pagos_ya_liquidados()
    return [
        p
        for p in store.pagos.values()
        if p.beneficiario_id == beneficiario_id and p.estado in ESTADOS_COBRADOS and p.id not in liquidados
    ]


def _neto_pago(pago: Pago) -> Decimal:
    return pago.monto - pago.monto_reembolsado


def generar_liquidacion(datos: LiquidacionCreate) -> Liquidacion:
    pagos = [
        p
        for p in _pagos_liquidables(datos.beneficiario_id)
        if datos.periodo_desde <= p.creado_en.date() <= datos.periodo_hasta
    ]
    if not pagos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No hay pagos pendientes de liquidar en el período indicado"
        )
    bruto = sum((_neto_pago(p) for p in pagos), Decimal("0"))
    comision = (bruto * COMISION_PLATAFORMA).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    ahora = datetime.now(timezone.utc)
    liquidacion = Liquidacion(
        id=uuid4(),
        beneficiario_id=datos.beneficiario_id,
        periodo_desde=datos.periodo_desde,
        periodo_hasta=datos.periodo_hasta,
        pago_ids=[p.id for p in pagos],
        monto_bruto=bruto,
        comision_plataforma=comision,
        monto_neto=bruto - comision,
        estado=EstadoLiquidacion.pendiente,
        creada_en=ahora,
        actualizada_en=ahora,
    )
    store.liquidaciones[liquidacion.id] = liquidacion
    return liquidacion


def obtener_liquidacion(liquidacion_id: UUID) -> Liquidacion:
    liquidacion = store.liquidaciones.get(liquidacion_id)
    if liquidacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liquidación no encontrada")
    return liquidacion


def listar_liquidaciones(beneficiario_id: UUID | None, estado: EstadoLiquidacion | None) -> list[Liquidacion]:
    return [
        liq
        for liq in store.liquidaciones.values()
        if (beneficiario_id is None or liq.beneficiario_id == beneficiario_id)
        and (estado is None or liq.estado == estado)
    ]


def _cambiar_estado(liquidacion_id: UUID, nuevo: EstadoLiquidacion, **extra) -> Liquidacion:
    liquidacion = obtener_liquidacion(liquidacion_id)
    if liquidacion.estado != EstadoLiquidacion.pendiente:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"La liquidación ya está en estado '{liquidacion.estado.value}'"
        )
    liquidacion = liquidacion.model_copy(
        update={"estado": nuevo, "actualizada_en": datetime.now(timezone.utc), **extra}
    )
    store.liquidaciones[liquidacion.id] = liquidacion
    return liquidacion


def confirmar_transferencia(liquidacion_id: UUID, datos: TransferenciaConfirmacion) -> Liquidacion:
    return _cambiar_estado(
        liquidacion_id, EstadoLiquidacion.transferida, referencia_transferencia=datos.referencia_transferencia
    )


def anular(liquidacion_id: UUID) -> Liquidacion:
    """Anula la liquidación y libera sus pagos para una nueva liquidación."""
    return _cambiar_estado(liquidacion_id, EstadoLiquidacion.anulada)


def obtener_saldo(beneficiario_id: UUID) -> Saldo:
    liquidaciones = listar_liquidaciones(beneficiario_id, None)
    return Saldo(
        beneficiario_id=beneficiario_id,
        saldo_pendiente_liquidar=sum(
            (_neto_pago(p) for p in _pagos_liquidables(beneficiario_id)), Decimal("0")
        ),
        liquidado_pendiente_transferir=sum(
            (liq.monto_neto for liq in liquidaciones if liq.estado == EstadoLiquidacion.pendiente), Decimal("0")
        ),
        total_transferido=sum(
            (liq.monto_neto for liq in liquidaciones if liq.estado == EstadoLiquidacion.transferida), Decimal("0")
        ),
    )
