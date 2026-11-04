from typing import Any, Dict

from fastapi import HTTPException

from app.api.v1.endpoints.contrato import registrar_tarifa_final
from app.core.database import get_db
from app.schemas.tarifas import TarifaFinalNueva


def procesar_viaje_finalizado(event: Dict[str, Any]) -> None:
    event_id = event["event_id"]
    event_type = event["event_type"]
    data = event["data"]

    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT event_id FROM eventos_mensajeria_procesados WHERE event_id=%s",
                (event_id,),
            )
            if cursor.fetchone():
                return

    try:
        registrar_tarifa_final(
            data["viaje_id"],
            TarifaFinalNueva(
                tipo_vehiculo=data["tipo_vehiculo"].lower(),
                distancia_real_km=float(data["distancia_real_km"]),
                duracion_real_min=float(data["duracion_real_min"]),
                multiplicador_demanda=float(data.get("multiplicador_demanda", 1)),
            ),
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            raise

    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT IGNORE INTO eventos_mensajeria_procesados (event_id, event_type)
                VALUES (%s, %s)
                """,
                (event_id, event_type),
            )
        conexion.commit()
