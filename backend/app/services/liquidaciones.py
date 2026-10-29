import uuid
from typing import Any, Dict, List

from app.core.database import get_db
from app.schemas.liquidaciones import LiquidacionRequest


def crear_liquidacion(datos: LiquidacionRequest) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            # 1. Chequeo de idempotencia
            cursor.execute(
                "SELECT * FROM liquidaciones WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            existente = cursor.fetchone()
            if existente:
                return {
                    "mensaje": "Liquidación ya registrada",
                    "liquidacion": existente,
                    "idempotency_key": datos.idempotency_key,
                }

            liquidacion_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO liquidaciones (
                    id, conductor_id, desde, hasta, cantidad_viajes, bruto, comision, neto, estado, idempotency_key, creado_en, actualizado_en
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', %s, NOW(), NOW())
                """,
                (
                    liquidacion_id,
                    datos.conductor_id,
                    datos.desde,
                    datos.hasta,
                    datos.cantidad_viajes,
                    datos.bruto,
                    datos.comision,
                    datos.neto,
                    datos.idempotency_key,
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM liquidaciones WHERE id = %s LIMIT 1", (liquidacion_id,))
            liquidacion = cursor.fetchone()
            return {
                "mensaje": "Liquidación creada",
                "liquidacion": liquidacion,
                "idempotency_key": datos.idempotency_key,
            }


def listar_liquidaciones_conductor(conductor_id: str) -> List[Dict[str, Any]]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM liquidaciones WHERE conductor_id = %s ORDER BY creado_en DESC",
                (conductor_id,),
            )
            return cursor.fetchall()
