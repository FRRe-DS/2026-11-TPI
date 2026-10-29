from typing import Any, Dict, List
from fastapi import APIRouter

from app.schemas.liquidaciones import LiquidacionRequest
from app.services import liquidaciones as liquidaciones_service

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])


@router.post("")
def crear_liquidacion(datos: LiquidacionRequest) -> Dict[str, Any]:
    """Crea una liquidación de haberes para un conductor con control de idempotencia."""
    return liquidaciones_service.crear_liquidacion(datos)


@router.get("/{conductor_id}")
def listar_liquidaciones_conductor(conductor_id: str) -> List[Dict[str, Any]]:
    """Lista las liquidaciones registradas para un conductor ordenadas por fecha."""
    return liquidaciones_service.listar_liquidaciones_conductor(conductor_id)
