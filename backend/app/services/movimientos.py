"""Historial financiero inmutable (RF-7.7). Solo se insertan filas, nunca se modifican."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.movimientos import MovimientoFinanciero, TipoMovimiento


def registrar(
    db: Session,
    tipo: TipoMovimiento,
    actor: str,
    monto: Decimal,
    *,
    pago: models.Pago | None = None,
    liquidacion: models.Liquidacion | None = None,
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    referencia: str | None = None,
    detalle: str | None = None,
) -> None:
    """Agrega el movimiento a la transacción en curso; lo confirma el commit de quien llama."""
    if pago is not None:
        viaje_id, cliente_id = pago.viaje_id, pago.cliente_id
    beneficiario_id = pago.beneficiario_id if pago else liquidacion.beneficiario_id if liquidacion else None
    estado = pago.estado if pago else liquidacion.estado if liquidacion else None
    db.add(
        models.MovimientoFinanciero(
            id=uuid4(),
            tipo=tipo.value,
            pago_id=pago.id if pago else None,
            liquidacion_id=liquidacion.id if liquidacion else None,
            viaje_id=viaje_id,
            cliente_id=cliente_id,
            beneficiario_id=beneficiario_id,
            monto=monto,
            moneda="ARS",
            estado_resultante=estado,
            referencia=referencia,
            detalle=detalle[:500] if detalle else None,
            actor=actor,
            creado_en=datetime.now(timezone.utc),
        )
    )


def listar(
    db: Session,
    pago_id: UUID | None = None,
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    beneficiario_id: UUID | None = None,
    liquidacion_id: UUID | None = None,
    tipo: TipoMovimiento | None = None,
) -> list[MovimientoFinanciero]:
    tabla = models.MovimientoFinanciero
    consulta = select(tabla).order_by(tabla.creado_en, tabla.id)
    for columna, valor in (
        (tabla.pago_id, pago_id),
        (tabla.viaje_id, viaje_id),
        (tabla.cliente_id, cliente_id),
        (tabla.beneficiario_id, beneficiario_id),
        (tabla.liquidacion_id, liquidacion_id),
        (tabla.tipo, tipo.value if tipo else None),
    ):
        if valor is not None:
            consulta = consulta.where(columna == valor)
    return [MovimientoFinanciero.model_validate(m) for m in db.scalars(consulta)]
