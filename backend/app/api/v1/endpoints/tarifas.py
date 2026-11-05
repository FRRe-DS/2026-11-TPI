from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tarifas import EstimacionRequest
from app.services.tarifas import calcular_estimacion_tarifa, obtener_todos_los_parametros

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])


@router.get("/parametros")
def obtener_parametros(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Obtiene los parámetros actuales de tarificación configurados en la base de datos."""
    return obtener_todos_los_parametros(db)


@router.post("/estimar")
def estimar_tarifa(
    datos: EstimacionRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Calcula la estimación de la tarifa según el tipo de vehículo, distancia y tiempo."""
    return calcular_estimacion_tarifa(datos, db)
