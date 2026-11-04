from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.medios_pago import MedioPagoRequest
from app.schemas.pagos import (
    CargoCancelacionRequest,
    PagoAutorizarRequest,
    PagoCapturarRequest,
    ReintegroRequest,
)
from app.services import medios_pago as medios_pago_service
from app.services import pagos as pagos_service

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.post("/medios")
def registrar_medio_pago(
    datos: MedioPagoRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Registra un nuevo medio de pago asociado a un cliente."""
    return medios_pago_service.registrar_medio_pago(datos, db)


@router.get("/medios/{cliente_id}")
def listar_medios_pago(
    cliente_id: str, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Lista todos los medios de pago asociados a un cliente."""
    return medios_pago_service.listar_medios_pago(cliente_id, db)


@router.post("/autorizar")
def autorizar_pago(
    datos: PagoAutorizarRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Autoriza un pago para un viaje respetando la idempotencia."""
    return pagos_service.autorizar_pago(datos, db)


@router.post("/capturar")
def capturar_pago(
    datos: PagoCapturarRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Captura un pago previamente autorizado confirmando el monto final."""
    return pagos_service.capturar_pago(datos, db)


@router.post("/cancelar")
def cancelar_pago(
    datos: CargoCancelacionRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Registra el cargo de cancelación cuando corresponda según las reglas de negocio."""
    return pagos_service.cancelar_pago(datos, db)


@router.post("/reintegrar")
def reintegrar_pago(
    datos: ReintegroRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Registra un reintegro total o parcial tras una cancelación o ajuste posterior."""
    return pagos_service.reintegrar_pago(datos, db)


@router.get("/{viaje_id}")
def obtener_pago_por_viaje(
    viaje_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Obtiene el estado y datos del pago correspondiente a un viaje."""
    return pagos_service.obtener_pago_por_viaje(viaje_id, db)


@router.get("/{viaje_id}/historial")
def historial_financiero(
    viaje_id: str, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Obtiene el historial de operaciones financieras registradas para un viaje."""
    return pagos_service.obtener_historial_financiero(viaje_id, db)
