from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.security import require_scope
from app.schemas.liquidaciones import (
    EstadoLiquidacion,
    Liquidacion,
    LiquidacionCreate,
    Saldo,
    TransferenciaConfirmacion,
)
from app.services import liquidaciones as service

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])
lectura = [Depends(require_scope("liquidaciones:read"))]
escritura = [Depends(require_scope("liquidaciones:write"))]


@router.post("", response_model=Liquidacion, status_code=status.HTTP_201_CREATED, dependencies=escritura)
def generar_liquidacion(datos: LiquidacionCreate):
    """Agrupa los pagos cobrados y no liquidados del beneficiario en el período y descuenta la comisión."""
    return service.generar_liquidacion(datos)


@router.get("", response_model=list[Liquidacion], dependencies=lectura)
def listar_liquidaciones(beneficiario_id: UUID | None = None, estado: EstadoLiquidacion | None = None):
    return service.listar_liquidaciones(beneficiario_id, estado)


@router.get("/saldos/{beneficiario_id}", response_model=Saldo, dependencies=lectura)
def obtener_saldo(beneficiario_id: UUID):
    return service.obtener_saldo(beneficiario_id)


@router.get("/{liquidacion_id}", response_model=Liquidacion, dependencies=lectura)
def obtener_liquidacion(liquidacion_id: UUID):
    return service.obtener_liquidacion(liquidacion_id)


@router.post("/{liquidacion_id}/transferencia", response_model=Liquidacion, dependencies=escritura)
def confirmar_transferencia(liquidacion_id: UUID, datos: TransferenciaConfirmacion):
    """Marca la liquidación como transferida al chofer/dueño."""
    return service.confirmar_transferencia(liquidacion_id, datos)


@router.post("/{liquidacion_id}/anulacion", response_model=Liquidacion, dependencies=escritura)
def anular_liquidacion(liquidacion_id: UUID):
    return service.anular(liquidacion_id)
