import re
import uuid
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.medios_pago import MedioPago
from app.schemas.medios_pago import MedioPagoRequest


def validar_medio_pago(datos: MedioPagoRequest) -> None:
    errores = []

    if datos.tipo not in {"tarjeta", "billetera", "efectivo"}:
        errores.append({
            "campo": "tipo",
            "error": "TIPO INVALIDO",
            "mensaje": "El tipo de medio de pago debe ser 'tarjeta', 'billetera virtual' o 'efectivo'.",
        })

    if not datos.alias or not datos.alias.strip():
        errores.append({
            "campo": "alias",
            "error": "ALIAS VACIO O INCOMPLETO",
            "mensaje": "El alias del medio de pago no puede estar vacío.",
        })

    if len(datos.alias.strip()) > 40:
        errores.append({
            "campo": "alias",
            "error": "ALIAS DEMASIADO LARGO",
            "mensaje": "El alias del medio de pago no puede superar los 40 caracteres.",
        })

    if datos.ultimos4 is not None:
        if not re.fullmatch(r"\d{4}", datos.ultimos4):
            errores.append({
                "campo": "ultimos4",
                "error": "ULTIMOS4 INVALIDO",
                "mensaje": "Los últimos 4 dígitos deben ser exactamente 4 números.",
            })

    if errores:
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_DATOS_INVALIDOS",
                "errores": errores,
            },
        )


def registrar_medio_pago(datos: MedioPagoRequest, db: Session) -> Dict[str, Any]:
    validar_medio_pago(datos)

    try:
        if datos.predeterminado:
            db.execute(
                update(MedioPago)
                .where(MedioPago.cliente_id == datos.cliente_id)
                .values(predeterminado=False)
            )

        nuevo_medio = MedioPago(
            id=str(uuid.uuid4()),
            cliente_id=datos.cliente_id,
            tipo=datos.tipo,
            alias=datos.alias.strip(),
            ultimos4=datos.ultimos4,
            predeterminado=datos.predeterminado,
        )
        db.add(nuevo_medio)
        db.commit()
        db.refresh(nuevo_medio)

        return {
            "id": nuevo_medio.id,
            "cliente_id": nuevo_medio.cliente_id,
            "tipo": nuevo_medio.tipo,
            "alias": nuevo_medio.alias,
            "ultimos4": nuevo_medio.ultimos4,
            "predeterminado": bool(nuevo_medio.predeterminado),
        }
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_MEDIO_PAGO_INVALIDO",
                "mensaje": "Los datos del medio de pago no cumplen las reglas de validación del sistema.",
                "detalle_db": str(exc),
            },
        ) from exc


def listar_medios_pago(cliente_id: str, db: Session) -> List[Dict[str, Any]]:
    medios = db.scalars(
        select(MedioPago)
        .where(MedioPago.cliente_id == cliente_id)
        .order_by(MedioPago.predeterminado.desc(), MedioPago.creado_en.desc())
    ).all()
    return [m.to_dict() for m in medios]
