import uuid
from datetime import datetime
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.medios_pago import MedioPago
from app.models.pagos import OperacionFinanciera, Pago
from app.models.tarifas import ParametroTarifa
from app.schemas.pagos import (
    CargoCancelacionRequest,
    PagoAutorizarRequest,
    PagoCapturarRequest,
    ReintegroRequest,
)


def autorizar_pago(datos: PagoAutorizarRequest, db: Session) -> Dict[str, Any]:
    # 1. Chequeo de idempotencia
    existente = db.scalar(
        select(OperacionFinanciera).where(
            OperacionFinanciera.idempotency_key == datos.idempotency_key
        )
    )
    if existente:
        pago_existente = db.scalar(select(Pago).where(Pago.id == existente.pago_id))
        if pago_existente:
            return {
                "mensaje": "Operación ya procesada",
                "pago": pago_existente.to_dict(),
                "idempotency_key": datos.idempotency_key,
            }

    # 2. Validar medio de pago si fue provisto
    if datos.medio_pago_id:
        medio = db.scalar(select(MedioPago).where(MedioPago.id == datos.medio_pago_id))
        if not medio:
            raise HTTPException(status_code=404, detail="M7_MEDIO_PAGO_NO_ENCONTRADO")

    # 3. Crear pago en estado autorizado
    pago_id = str(uuid.uuid4())
    ahora = datetime.now()
    nuevo_pago = Pago(
        id=pago_id,
        viaje_id=datos.viaje_id,
        cliente_id=datos.cliente_id,
        conductor_id=datos.conductor_id,
        medio_pago_id=datos.medio_pago_id,
        tipo_vehiculo=datos.tipo_vehiculo,
        monto_estimado=datos.monto_estimado,
        monto_final=None,
        comision_pct=datos.comision_pct if datos.comision_pct is not None else 0,
        estado="autorizado",
        capturado_en=None,
        liquidacion_id=None,
        creado_en=ahora,
        actualizado_en=ahora,
    )
    db.add(nuevo_pago)

    # 4. Registrar operación financiera
    operacion = OperacionFinanciera(
        id=str(uuid.uuid4()),
        pago_id=pago_id,
        tipo="autorizacion",
        monto=datos.monto_estimado,
        resultado="ok",
        motivo="Autorización OK",
        idempotency_key=datos.idempotency_key,
        detalle={
            "viaje_id": datos.viaje_id,
            "cliente_id": datos.cliente_id,
            "medio_pago_id": datos.medio_pago_id,
            "monto_estimado": datos.monto_estimado,
        },
        creado_en=ahora,
    )
    db.add(operacion)
    db.commit()
    db.refresh(nuevo_pago)

    return {
        "mensaje": "Pago autorizado",
        "pago": nuevo_pago.to_dict(),
        "idempotency_key": datos.idempotency_key,
    }


def capturar_pago(datos: PagoCapturarRequest, db: Session) -> Dict[str, Any]:
    # 1. Chequeo de idempotencia
    operacion_existente = db.scalar(
        select(OperacionFinanciera).where(
            OperacionFinanciera.idempotency_key == datos.idempotency_key
        )
    )
    if operacion_existente:
        pago_existente = db.scalar(
            select(Pago).where(Pago.id == operacion_existente.pago_id)
        )
        if pago_existente:
            return {
                "mensaje": "Captura ya procesada",
                "pago": pago_existente.to_dict(),
                "idempotency_key": datos.idempotency_key,
            }

    # 2. Validar existencia del pago
    pago = db.scalar(select(Pago).where(Pago.id == datos.pago_id))
    if not pago:
        raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

    if pago.estado not in ["autorizado", "cancelado_con_cargo"]:
        raise HTTPException(
            status_code=409, detail="M7_PAGO_ESTADO_NO_PERMITE_CAPTURA"
        )

    ahora = datetime.now()
    monto_final = (
        float(datos.monto_final)
        if datos.monto_final is not None
        else float(pago.monto_estimado)
    )
    pago.monto_final = monto_final
    pago.estado = "capturado"
    pago.capturado_en = ahora
    pago.actualizado_en = ahora

    operacion = OperacionFinanciera(
        id=str(uuid.uuid4()),
        pago_id=datos.pago_id,
        tipo="captura",
        monto=monto_final,
        resultado="ok",
        motivo="Captura exitosa",
        idempotency_key=datos.idempotency_key,
        detalle={"monto_final": monto_final, "pago_id": datos.pago_id},
        creado_en=ahora,
    )
    db.add(operacion)
    db.commit()
    db.refresh(pago)

    return {
        "mensaje": "Pago capturado",
        "pago": pago.to_dict(),
        "idempotency_key": datos.idempotency_key,
    }


def cancelar_pago(datos: CargoCancelacionRequest, db: Session) -> Dict[str, Any]:
    # 1. Chequeo de idempotencia
    operacion_existente = db.scalar(
        select(OperacionFinanciera).where(
            OperacionFinanciera.idempotency_key == datos.idempotency_key
        )
    )
    if operacion_existente:
        pago_existente = db.scalar(
            select(Pago).where(Pago.id == operacion_existente.pago_id)
        )
        if pago_existente:
            return {
                "mensaje": "Cargo de cancelación ya registrado",
                "pago": pago_existente.to_dict(),
                "idempotency_key": datos.idempotency_key,
            }

    pago = db.scalar(select(Pago).where(Pago.id == datos.pago_id))
    if not pago:
        raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

    param = db.scalar(
        select(ParametroTarifa).where(
            ParametroTarifa.tipo_vehiculo == pago.tipo_vehiculo
        )
    )
    cargo = float(param.cargo_cancelacion) if param else 0.0

    ahora = datetime.now()
    if pago.monto_final is None:
        pago.monto_final = pago.monto_estimado
    pago.estado = "cancelado_con_cargo"
    pago.actualizado_en = ahora

    operacion = OperacionFinanciera(
        id=str(uuid.uuid4()),
        pago_id=datos.pago_id,
        tipo="cargo_cancelacion",
        monto=cargo,
        resultado="ok",
        motivo=datos.motivo,
        idempotency_key=datos.idempotency_key,
        detalle={"cargo_cancelacion": cargo, "motivo": datos.motivo},
        creado_en=ahora,
    )
    db.add(operacion)
    db.commit()
    db.refresh(pago)

    return {
        "mensaje": "Cargo de cancelación registrado",
        "cargo": cargo,
        "pago": pago.to_dict(),
        "idempotency_key": datos.idempotency_key,
    }


def reintegrar_pago(datos: ReintegroRequest, db: Session) -> Dict[str, Any]:
    # 1. Chequeo de idempotencia
    operacion_existente = db.scalar(
        select(OperacionFinanciera).where(
            OperacionFinanciera.idempotency_key == datos.idempotency_key
        )
    )
    if operacion_existente:
        pago_existente = db.scalar(
            select(Pago).where(Pago.id == operacion_existente.pago_id)
        )
        if pago_existente:
            return {
                "mensaje": "Reintegro ya registrado",
                "pago": pago_existente.to_dict(),
                "idempotency_key": datos.idempotency_key,
            }

    pago = db.scalar(select(Pago).where(Pago.id == datos.pago_id))
    if not pago:
        raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

    monto_total = (
        float(pago.monto_final)
        if pago.monto_final is not None
        else float(pago.monto_estimado)
    )
    if float(datos.monto) < 0 or float(datos.monto) > monto_total:
        raise HTTPException(status_code=400, detail="M7_MONTO_REINTEGRO_INVALIDO")

    nuevo_estado = (
        "reintegrado" if float(datos.monto) >= monto_total else "reintegrado_parcial"
    )
    ahora = datetime.now()
    pago.estado = nuevo_estado
    pago.actualizado_en = ahora

    operacion = OperacionFinanciera(
        id=str(uuid.uuid4()),
        pago_id=datos.pago_id,
        tipo="reintegro",
        monto=datos.monto,
        resultado="ok",
        motivo=datos.motivo,
        idempotency_key=datos.idempotency_key,
        detalle={"monto_reintegrado": datos.monto, "estado": nuevo_estado},
        creado_en=ahora,
    )
    db.add(operacion)
    db.commit()
    db.refresh(pago)

    return {
        "mensaje": "Reintegro registrado",
        "pago": pago.to_dict(),
        "monto_reintegrado": datos.monto,
        "idempotency_key": datos.idempotency_key,
    }


def obtener_pago_por_viaje(viaje_id: str, db: Session) -> Dict[str, Any]:
    pago = db.scalar(select(Pago).where(Pago.viaje_id == viaje_id))
    if not pago:
        raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
    return pago.to_dict()


def obtener_historial_financiero(viaje_id: str, db: Session) -> List[Dict[str, Any]]:
    pago = db.scalar(select(Pago).where(Pago.viaje_id == viaje_id))
    if not pago:
        raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
    operaciones = db.scalars(
        select(OperacionFinanciera)
        .where(OperacionFinanciera.pago_id == pago.id)
        .order_by(OperacionFinanciera.creado_en.desc())
    ).all()
    return [op.to_dict() for op in operaciones]
