from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import CLIENTE, OPERADOR, SERVICIO, Usuario, require_scope, verificar_cliente
from app.db.session import get_db
from app.schemas.cancelaciones import CancelacionCreate, CargoCancelacion
from app.services import cancelaciones as service
from app.services.integraciones import ViajesM6, obtener_m6
from app.services.pasarela import PasarelaPagos, obtener_pasarela

router = APIRouter(prefix="/cancelaciones", tags=["Cancelaciones"])


@router.post("", response_model=CargoCancelacion, status_code=status.HTTP_201_CREATED)
def registrar_cancelacion(
    datos: CancelacionCreate,
    usuario: Usuario = Depends(require_scope("pagos:write", CLIENTE, SERVICIO, OPERADOR)),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
    m6: ViajesM6 | None = Depends(obtener_m6),
):
    """Calcula y registra el cargo de cancelación según el estado del viaje (RF-7.4).

    Anula la autorización del viaje y, si corresponde un cargo, lo cobra con el mismo medio de pago.
    Sin estado_viaje en el cuerpo, el estado se consulta a M6.
    """
    verificar_cliente(usuario, datos.cliente_id)
    return service.registrar(db, datos, usuario, pasarela, m6)


@router.get("/{viaje_id}", response_model=CargoCancelacion)
def obtener_cancelacion(
    viaje_id: UUID, usuario: Usuario = Depends(require_scope("pagos:read")), db: Session = Depends(get_db)
):
    cargo = service.obtener(db, viaje_id)
    verificar_cliente(usuario, cargo.cliente_id)
    return CargoCancelacion.model_validate(cargo)
