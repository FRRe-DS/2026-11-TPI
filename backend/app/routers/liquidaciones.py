from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import OPERADOR, SERVICIO, Usuario, filtro_propio, require_scope, verificar_beneficiario
from app.db.session import get_db
from app.schemas.liquidaciones import (
    EstadoLiquidacion,
    Liquidacion,
    LiquidacionCreate,
    Saldo,
    TransferenciaConfirmacion,
)
from app.services import liquidaciones as service

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])
lectura = require_scope("liquidaciones:read")
solo_operador = require_scope("liquidaciones:write", OPERADOR)


@router.post("", response_model=Liquidacion, status_code=status.HTTP_201_CREATED)
def generar_liquidacion(
    datos: LiquidacionCreate,
    usuario: Usuario = Depends(require_scope("liquidaciones:write", OPERADOR, SERVICIO)),
    db: Session = Depends(get_db),
):
    """Agrupa los pagos cobrados y no liquidados del beneficiario en el período y descuenta la comisión."""
    return service.generar_liquidacion(db, datos, usuario)


@router.get("", response_model=list[Liquidacion])
def listar_liquidaciones(
    beneficiario_id: UUID | None = None,
    estado: EstadoLiquidacion | None = None,
    usuario: Usuario = Depends(lectura),
    db: Session = Depends(get_db),
):
    """Un conductor ve solo sus liquidaciones."""
    _, beneficiario_id = filtro_propio(usuario, None, beneficiario_id)
    return service.listar_liquidaciones(db, beneficiario_id, estado)


@router.get("/saldos/{beneficiario_id}", response_model=Saldo)
def obtener_saldo(beneficiario_id: UUID, usuario: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    verificar_beneficiario(usuario, beneficiario_id)
    return service.obtener_saldo(db, beneficiario_id)


@router.get("/{liquidacion_id}", response_model=Liquidacion)
def obtener_liquidacion(liquidacion_id: UUID, usuario: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    liquidacion = service.obtener_liquidacion(db, liquidacion_id)
    verificar_beneficiario(usuario, liquidacion.beneficiario_id)
    return liquidacion


@router.post("/{liquidacion_id}/transferencia", response_model=Liquidacion)
def confirmar_transferencia(
    liquidacion_id: UUID,
    datos: TransferenciaConfirmacion,
    usuario: Usuario = Depends(solo_operador),
    db: Session = Depends(get_db),
):
    """Marca la liquidación como transferida al chofer/dueño. Solo operador."""
    return service.confirmar_transferencia(db, liquidacion_id, datos, usuario)


@router.post("/{liquidacion_id}/anulacion", response_model=Liquidacion)
def anular_liquidacion(liquidacion_id: UUID, usuario: Usuario = Depends(solo_operador), db: Session = Depends(get_db)):
    """Anula la liquidación y libera sus pagos. Solo operador."""
    return service.anular(db, liquidacion_id, usuario)
