from typing import Any, Dict, List
from fastapi import HTTPException

from app.core.database import get_db
from app.schemas.tarifas import EstimacionRequest


def validar_datos_estimacion(datos: EstimacionRequest) -> List[Dict[str, str]]:
    errores = []

    if datos.tipo_vehiculo.lower() not in ["auto", "moto"]:
        errores.append({
            "campo": "tipo_vehiculo",
            "error": "VEHICULO INVALIDO",
            "mensaje": f"El tipo de vehículo '{datos.tipo_vehiculo}' no es válido. Debe ser 'auto' o 'moto'."
        })

    if datos.distancia_km < 0:
        errores.append({
            "campo": "distancia_km",
            "error": "DISTANCIA NEGATIVA",
            "mensaje": "La distancia en km no puede ser negativa."
        })

    if datos.tiempo_min <= 0:
        errores.append({
            "campo": "tiempo_min",
            "error": "TIEMPO INVALIDO",
            "mensaje": "El tiempo en minutos debe ser mayor a 0."
        })

    return errores


def obtener_todos_los_parametros() -> List[Dict[str, Any]]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM parametros_tarifa")
            return cursor.fetchall()


def calcular_estimacion_tarifa(datos: EstimacionRequest) -> Dict[str, Any]:
    errores = validar_datos_estimacion(datos)
    if errores:
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_DATOS_INVALIDOS",
                "errores": errores,
            },
        )

    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM parametros_tarifa WHERE tipo_vehiculo = %s",
                (datos.tipo_vehiculo.lower(),),
            )
            param = cursor.fetchone()

            if not param:
                raise HTTPException(status_code=404, detail="M7_SIN_PARAMETROS")

            base = float(param["base"])
            por_km = float(param["por_km"])
            por_min = float(param["por_min"])
            minima = float(param["minima"])

            costo_distancia = round(por_km * datos.distancia_km, 2)
            costo_tiempo = round(por_min * datos.tiempo_min, 2)
            subtotal = base + costo_distancia + costo_tiempo
            total = round(max(subtotal, minima), 2)

            return {
                "tipo_vehiculo": datos.tipo_vehiculo.lower(),
                "base": base,
                "distancia": costo_distancia,
                "tiempo": costo_tiempo,
                "minima": minima,
                "minima_aplicada": subtotal < minima,
                "total": total,
                "moneda": "ARS",
            }
