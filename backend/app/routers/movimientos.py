from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Usuario, filtro_propio, require_scope
from app.db.session import get_db
from app.schemas.movimientos import MovimientoFinanciero, TipoMovimiento
from app.services import movimientos as service

router = APIRouter(prefix="/movimientos", tags=["Historial financiero"])


@router.get("", response_model=list[MovimientoFinanciero])
def listar_movimientos(
    pago_id: UUID | None = None,
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    beneficiario_id: UUID | None = None,
    liquidacion_id: UUID | None = None,
    tipo: TipoMovimiento | None = None,
    usuario: Usuario = Depends(require_scope("pagos:read")),
    db: Session = Depends(get_db),
):
    """Historial inmutable de autorizaciones, capturas, rechazos, cargos, reembolsos y liquidaciones (RF-7.7).

    Un cliente ve solo sus movimientos y un conductor los que lo tienen de beneficiario.
    """
    cliente_id, beneficiario_id = filtro_propio(usuario, cliente_id, beneficiario_id)
    return service.listar(db, pago_id, viaje_id, cliente_id, beneficiario_id, liquidacion_id, tipo)
