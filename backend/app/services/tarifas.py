from typing import Any, Dict, List
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis import eliminar_cache_patron, guardar_cache, obtener_cache
from app.models.tarifas import ParametroTarifa
from app.schemas.tarifas import EstimacionRequest

CLAVE_CACHE_TODOS = "tarifas:parametros:todos"
PREFIJO_CACHE_PARAMETRO = "tarifas:parametro:"


def validar_datos_estimacion(datos: EstimacionRequest) -> List[Dict[str, str]]:
    errores = []

    if datos.tipo_vehiculo.lower() not in ["auto", "moto"]:
        errores.append({
            "campo": "tipo_vehiculo",
            "error": "VEHICULO INVALIDO",
            "mensaje": f"El tipo de vehículo '{datos.tipo_vehiculo}' no es válido. Debe ser 'auto' o 'moto'.",
        })

    if datos.distancia_km < 0:
        errores.append({
            "campo": "distancia_km",
            "error": "DISTANCIA NEGATIVA",
            "mensaje": "La distancia en km no puede ser negativa.",
        })

    if datos.tiempo_min <= 0:
        errores.append({
            "campo": "tiempo_min",
            "error": "TIEMPO INVALIDO",
            "mensaje": "El tiempo en minutos debe ser mayor a 0.",
        })

    return errores


def invalidar_cache_tarifas() -> None:
    """Invalida todas las claves de parámetros de tarifas cacheadas en Redis."""
    eliminar_cache_patron("tarifas:*")


def obtener_todos_los_parametros(db: Session) -> List[Dict[str, Any]]:
    # 1. Intentar responder desde la caché en memoria (Redis - RNF-11)
    cacheados = obtener_cache(CLAVE_CACHE_TODOS)
    if cacheados is not None:
        return cacheados

    # 2. Si no está en caché (cache miss) o Redis está inactivo, consultar la BD relacional
    parametros = db.scalars(select(ParametroTarifa)).all()
    resultado = [p.to_dict() for p in parametros]

    # 3. Guardar en Redis para futuras lecturas ultrarrápidas
    guardar_cache(CLAVE_CACHE_TODOS, resultado)
    for p in parametros:
        guardar_cache(f"{PREFIJO_CACHE_PARAMETRO}{p.tipo_vehiculo.lower()}", p.to_dict())

    return resultado


def calcular_estimacion_tarifa(datos: EstimacionRequest, db: Session) -> Dict[str, Any]:
    errores = validar_datos_estimacion(datos)
    if errores:
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_DATOS_INVALIDOS",
                "errores": errores,
            },
        )

    tipo = datos.tipo_vehiculo.lower()
    clave_cache = f"{PREFIJO_CACHE_PARAMETRO}{tipo}"

    # 1. Intentar obtener el parámetro del vehículo desde Redis
    param_dict = obtener_cache(clave_cache)

    if param_dict is None:
        # 2. Cache miss: consultar en base de datos
        param = db.scalar(
            select(ParametroTarifa).where(
                ParametroTarifa.tipo_vehiculo == tipo
            )
        )
        if not param:
            raise HTTPException(status_code=404, detail="M7_SIN_PARAMETROS")

        param_dict = param.to_dict()
        # 3. Almacenar en Redis
        guardar_cache(clave_cache, param_dict)

    base = float(param_dict["base"])
    por_km = float(param_dict["por_km"])
    por_min = float(param_dict["por_min"])
    minima = float(param_dict["minima"])

    costo_distancia = round(por_km * datos.distancia_km, 2)
    costo_tiempo = round(por_min * datos.tiempo_min, 2)
    subtotal = base + costo_distancia + costo_tiempo
    total = round(max(subtotal, minima), 2)

    return {
        "tipo_vehiculo": tipo,
        "base": base,
        "distancia": costo_distancia,
        "tiempo": costo_tiempo,
        "minima": minima,
        "minima_aplicada": subtotal < minima,
        "total": total,
        "moneda": "ARS",
    }
