from typing import Any, Dict, List
from fastapi import APIRouter

from app.schemas.tarifas import EstimacionRequest
from app.services.tarifas import calcular_estimacion_tarifa, obtener_todos_los_parametros

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])


@router.get("/parametros")
def obtener_parametros() -> List[Dict[str, Any]]:
    """Obtiene los parámetros actuales de tarificación configurados en la base de datos."""
    return obtener_todos_los_parametros()


@router.post("/estimar")
def estimar_tarifa(datos: EstimacionRequest) -> Dict[str, Any]:
    """Calcula la estimación de la tarifa según el tipo de vehículo, distancia y tiempo."""
    return calcular_estimacion_tarifa(datos)
