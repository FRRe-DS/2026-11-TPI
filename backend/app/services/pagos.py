import json
import uuid
from typing import Any, Dict, List
from fastapi import HTTPException

from app.core.database import get_db
from app.schemas.pagos import (
    CargoCancelacionRequest,
    PagoAutorizarRequest,
    PagoCapturarRequest,
    ReintegroRequest,
)


def autorizar_pago(datos: PagoAutorizarRequest) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            # 1. Chequeo de idempotencia
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            existente = cursor.fetchone()
            if existente:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (existente["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {
                        "mensaje": "Operación ya procesada",
                        "pago": pago_existente,
                        "idempotency_key": datos.idempotency_key,
                    }

            # 2. Validar medio de pago si fue provisto
            if datos.medio_pago_id:
                cursor.execute(
                    "SELECT * FROM medios_pago WHERE id = %s LIMIT 1",
                    (datos.medio_pago_id,),
                )
                medio = cursor.fetchone()
                if not medio:
                    raise HTTPException(status_code=404, detail="M7_MEDIO_PAGO_NO_ENCONTRADO")

            # 3. Crear pago en estado autorizado
            pago_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO pagos (
                    id, viaje_id, cliente_id, conductor_id, medio_pago_id, tipo_vehiculo,
                    monto_estimado, monto_final, comision_pct, estado, capturado_en,
                    liquidacion_id, creado_en, actualizado_en
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, 'autorizado', NULL, NULL, NOW(), NOW())
                """,
                (
                    pago_id,
                    datos.viaje_id,
                    datos.cliente_id,
                    datos.conductor_id,
                    datos.medio_pago_id,
                    datos.tipo_vehiculo,
                    datos.monto_estimado,
                    datos.comision_pct if datos.comision_pct is not None else 0,
                ),
            )

            # 4. Registrar operación financiera
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (
                    id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en
                )
                VALUES (%s, %s, 'autorizacion', %s, 'ok', 'Autorización OK', %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    pago_id,
                    datos.monto_estimado,
                    datos.idempotency_key,
                    json.dumps({
                        "viaje_id": datos.viaje_id,
                        "cliente_id": datos.cliente_id,
                        "medio_pago_id": datos.medio_pago_id,
                        "monto_estimado": datos.monto_estimado,
                    }),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (pago_id,))
            pago = cursor.fetchone()
            return {
                "mensaje": "Pago autorizado",
                "pago": pago,
                "idempotency_key": datos.idempotency_key,
            }


def capturar_pago(datos: PagoCapturarRequest) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            # 1. Chequeo de idempotencia
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {
                        "mensaje": "Captura ya procesada",
                        "pago": pago_existente,
                        "idempotency_key": datos.idempotency_key,
                    }

            # 2. Validar existencia del pago
            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            if pago["estado"] not in ["autorizado", "cancelado_con_cargo"]:
                raise HTTPException(status_code=409, detail="M7_PAGO_ESTADO_NO_PERMITE_CAPTURA")

            monto_final = float(datos.monto_final) if datos.monto_final is not None else float(pago["monto_estimado"])
            cursor.execute(
                "UPDATE pagos SET monto_final = %s, estado = 'capturado', capturado_en = NOW(), actualizado_en = NOW() WHERE id = %s",
                (monto_final, datos.pago_id),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'captura', %s, 'ok', 'Captura exitosa', %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    monto_final,
                    datos.idempotency_key,
                    json.dumps({"monto_final": monto_final, "pago_id": datos.pago_id}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {
                "mensaje": "Pago capturado",
                "pago": pago_actualizado,
                "idempotency_key": datos.idempotency_key,
            }


def cancelar_pago(datos: CargoCancelacionRequest) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            # 1. Chequeo de idempotencia
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {
                        "mensaje": "Cargo de cancelación ya registrado",
                        "pago": pago_existente,
                        "idempotency_key": datos.idempotency_key,
                    }

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            cursor.execute(
                "SELECT cargo_cancelacion FROM parametros_tarifa WHERE tipo_vehiculo = %s LIMIT 1",
                (pago["tipo_vehiculo"],),
            )
            param = cursor.fetchone()
            cargo = float(param["cargo_cancelacion"]) if param else 0.0

            cursor.execute(
                "UPDATE pagos SET monto_final = COALESCE(monto_final, monto_estimado), estado = 'cancelado_con_cargo', actualizado_en = NOW() WHERE id = %s",
                (datos.pago_id,),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'cargo_cancelacion', %s, 'ok', %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    cargo,
                    datos.motivo,
                    datos.idempotency_key,
                    json.dumps({"cargo_cancelacion": cargo, "motivo": datos.motivo}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {
                "mensaje": "Cargo de cancelación registrado",
                "cargo": cargo,
                "pago": pago_actualizado,
                "idempotency_key": datos.idempotency_key,
            }


def reintegrar_pago(datos: ReintegroRequest) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            # 1. Chequeo de idempotencia
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {
                        "mensaje": "Reintegro ya registrado",
                        "pago": pago_existente,
                        "idempotency_key": datos.idempotency_key,
                    }

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            monto_total = float(pago["monto_final"]) if pago["monto_final"] is not None else float(pago["monto_estimado"])
            if float(datos.monto) < 0 or float(datos.monto) > monto_total:
                raise HTTPException(status_code=400, detail="M7_MONTO_REINTEGRO_INVALIDO")

            nuevo_estado = "reintegrado" if float(datos.monto) >= monto_total else "reintegrado_parcial"
            cursor.execute(
                "UPDATE pagos SET estado = %s, actualizado_en = NOW() WHERE id = %s",
                (nuevo_estado, datos.pago_id),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'reintegro', %s, 'ok', %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    datos.monto,
                    datos.motivo,
                    datos.idempotency_key,
                    json.dumps({"monto_reintegrado": datos.monto, "estado": nuevo_estado}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {
                "mensaje": "Reintegro registrado",
                "pago": pago_actualizado,
                "monto_reintegrado": datos.monto,
                "idempotency_key": datos.idempotency_key,
            }


def obtener_pago_por_viaje(viaje_id: str) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM pagos WHERE viaje_id = %s LIMIT 1", (viaje_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
            return pago


def obtener_historial_financiero(viaje_id: str) -> List[Dict[str, Any]]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM pagos WHERE viaje_id = %s LIMIT 1", (viaje_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE pago_id = %s ORDER BY creado_en DESC",
                (pago["id"],),
            )
            return cursor.fetchall()
