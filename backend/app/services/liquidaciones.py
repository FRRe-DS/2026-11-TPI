import uuid
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.liquidaciones import Liquidacion
from app.schemas.liquidaciones import LiquidacionRequest


def crear_liquidacion(datos: LiquidacionRequest, db: Session) -> Dict[str, Any]:
    # 1. Chequeo de idempotencia
    existente = db.scalar(
        select(Liquidacion).where(
            Liquidacion.idempotency_key == datos.idempotency_key
        )
    )
    if existente:
        return {
            "mensaje": "Liquidación ya registrada",
            "liquidacion": existente.to_dict(),
            "idempotency_key": datos.idempotency_key,
        }

    ahora = datetime.now()
    desde_dt = (
        datetime.fromisoformat(datos.desde)
        if isinstance(datos.desde, str)
        else datos.desde
    )
    hasta_dt = (
        datetime.fromisoformat(datos.hasta)
        if isinstance(datos.hasta, str)
        else datos.hasta
    )

    liquidacion = Liquidacion(
        id=str(uuid.uuid4()),
        conductor_id=datos.conductor_id,
        desde=desde_dt,
        hasta=hasta_dt,
        cantidad_viajes=datos.cantidad_viajes,
        bruto=datos.bruto,
        comision=datos.comision,
        neto=datos.neto,
        estado="pendiente",
        idempotency_key=datos.idempotency_key,
        creado_en=ahora,
        actualizado_en=ahora,
    )
    db.add(liquidacion)
    db.commit()
    db.refresh(liquidacion)

    return {
        "mensaje": "Liquidación creada",
        "liquidacion": liquidacion.to_dict(),
        "idempotency_key": datos.idempotency_key,
    }


def listar_liquidaciones_conductor(
    conductor_id: str, db: Session
) -> List[Dict[str, Any]]:
    liquidaciones = db.scalars(
        select(Liquidacion)
        .where(Liquidacion.conductor_id == conductor_id)
        .order_by(Liquidacion.creado_en.desc())
    ).all()
    return [liq.to_dict() for liq in liquidaciones]
