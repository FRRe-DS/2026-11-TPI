"""Cargo de cancelación (RF-7.4). Las reglas son supuestos a acordar con el consorcio."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflicto, no_encontrado, no_procesable
from app.core.security import Usuario
from app.db import models
from app.schemas.cancelaciones import CancelacionCreate, CargoCancelacion, EstadoViaje, ReglaCargo
from app.schemas.movimientos import TipoMovimiento
from app.schemas.pagos import EstadoPago
from app.services import movimientos, pagos
from app.services.integraciones import ViajesM6
from app.services.pasarela import PasarelaPagos

CERO = Decimal("0")


@dataclass(frozen=True)
class ReglasCancelacion:
    periodo_gracia: timedelta
    cargo_asignado: Decimal
    cargo_conductor_en_punto: Decimal

    @classmethod
    def desde_configuracion(cls) -> "ReglasCancelacion":
        return cls(
            periodo_gracia=timedelta(minutes=settings.cancelacion_periodo_gracia_min),
            cargo_asignado=settings.cancelacion_cargo_asignado,
            cargo_conductor_en_punto=settings.cancelacion_cargo_conductor_en_punto,
        )


def calcular_cargo(
    estado: EstadoViaje,
    asignado_en: datetime | None,
    cancelado_en: datetime,
    reglas: ReglasCancelacion,
) -> tuple[Decimal, ReglaCargo]:
    """Regla pura del cargo según el estado del viaje al cancelar.

    - Antes de la asignación: sin cargo.
    - Asignado y dentro del período de gracia: sin cargo.
    - Asignado y pasado el período de gracia: cargo fijo.
    - Conductor en el punto de retiro: cargo mayor.
    - En curso, finalizado o ya cancelado: no se puede cancelar.
    """
    if estado == EstadoViaje.solicitado:
        return CERO, ReglaCargo.sin_asignar
    if estado == EstadoViaje.conductor_en_punto:
        return reglas.cargo_conductor_en_punto, ReglaCargo.conductor_en_punto
    if estado == EstadoViaje.asignado:
        if asignado_en is None:
            raise no_procesable(
                "falta-asignado-en",
                "Falta el momento de asignación",
                "Para un viaje asignado se necesita asignado_en para aplicar el período de gracia",
            )
        if cancelado_en - asignado_en <= reglas.periodo_gracia:
            return CERO, ReglaCargo.dentro_periodo_gracia
        return reglas.cargo_asignado, ReglaCargo.asignado_fuera_de_gracia
    raise no_procesable(
        "viaje-no-cancelable", "El viaje no se puede cancelar", f"El viaje está en estado '{estado.value}'"
    )


def _estado_del_viaje(datos: CancelacionCreate, m6: ViajesM6 | None) -> tuple[EstadoViaje, datetime | None]:
    if datos.estado_viaje is not None:
        return datos.estado_viaje, datos.asignado_en
    if m6 is None:
        raise no_procesable(
            "estado-viaje-desconocido",
            "No se conoce el estado del viaje",
            "M6 no está configurado: enviar estado_viaje (y asignado_en si está asignado)",
        )
    viaje = m6.obtener_viaje(datos.viaje_id)
    try:
        estado = EstadoViaje(viaje.estado)
    except ValueError as exc:
        raise no_procesable("estado-viaje-desconocido", "M6 informó un estado desconocido", viaje.estado) from exc
    return estado, datos.asignado_en or viaje.asignado_en


def registrar(
    db: Session, datos: CancelacionCreate, usuario: Usuario, pasarela: PasarelaPagos, m6: ViajesM6 | None = None
) -> CargoCancelacion:
    if db.scalar(select(models.CargoCancelacion).where(models.CargoCancelacion.viaje_id == datos.viaje_id)):
        raise conflicto("cancelacion-duplicada", "El viaje ya tiene una cancelación registrada")

    estado, asignado_en = _estado_del_viaje(datos, m6)
    cancelado_en = datos.cancelado_en or datetime.now(timezone.utc)
    monto, regla = calcular_cargo(estado, asignado_en, cancelado_en, ReglasCancelacion.desde_configuracion())

    pago_viaje = pagos.cobro_vigente(db, datos.viaje_id)
    if pago_viaje is not None and pago_viaje.cliente_id != datos.cliente_id:
        raise no_procesable("cliente-no-coincide", "El cobro del viaje pertenece a otro cliente")
    pago_anulado_id = None
    if pago_viaje is not None and pago_viaje.estado == EstadoPago.autorizado:
        pago_anulado_id = pagos.anular(db, pago_viaje.id, usuario.sub, pasarela, f"Cancelación: {datos.motivo}").id

    cargo = models.CargoCancelacion(
        id=uuid4(),
        viaje_id=datos.viaje_id,
        cliente_id=datos.cliente_id,
        estado_viaje=estado.value,
        regla_aplicada=regla.value,
        monto=monto,
        moneda="ARS",
        motivo=datos.motivo,
        pago_anulado_id=pago_anulado_id,
        creado_por=usuario.sub,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(cargo)
    movimientos.registrar(
        db,
        TipoMovimiento.cargo_cancelacion,
        usuario.sub,
        monto,
        viaje_id=datos.viaje_id,
        cliente_id=datos.cliente_id,
        detalle=f"{regla.value}: {datos.motivo}",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflicto("cancelacion-duplicada", "El viaje ya tiene una cancelación registrada") from exc

    # Sin medio de pago autorizado el cargo queda registrado para cobrarse por otra vía
    if monto > 0 and pago_viaje is not None:
        cargo.pago_cargo_id = pagos.cobrar_cargo(db, pago_viaje, monto, usuario.sub, pasarela).id
        db.add(cargo)
        db.commit()
    return CargoCancelacion.model_validate(cargo)


def obtener(db: Session, viaje_id) -> models.CargoCancelacion:
    cargo = db.scalar(select(models.CargoCancelacion).where(models.CargoCancelacion.viaje_id == viaje_id))
    if cargo is None:
        raise no_encontrado("El viaje no tiene una cancelación registrada")
    return cargo
