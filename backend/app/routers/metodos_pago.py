from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.security import CLIENTE, OPERADOR, Usuario, filtro_propio, require_scope, verificar_cliente
from app.db.session import get_db
from app.schemas.metodos_pago import MetodoPago, MetodoPagoCreate
from app.services import metodos_pago as service
from app.services.pasarela import PasarelaPagos, obtener_pasarela

router = APIRouter(prefix="/metodos-pago", tags=["Métodos de pago"])
lectura = require_scope("pagos:read")
escritura = require_scope("pagos:write", CLIENTE, OPERADOR)


@router.post("", response_model=MetodoPago, status_code=status.HTTP_201_CREATED)
def registrar_metodo_pago(
    datos: MetodoPagoCreate,
    response: Response,
    usuario: Usuario = Depends(escritura),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
):
    """Registra un medio de pago. El número de tarjeta se tokeniza y no se guarda; no se acepta CVV."""
    verificar_cliente(usuario, datos.cliente_id)
    metodo = service.crear(db, datos, pasarela)
    response.headers["Location"] = f"/api/v1/metodos-pago/{metodo.id}"
    return metodo


@router.get("", response_model=list[MetodoPago])
def listar_metodos_pago(
    cliente_id: UUID | None = None,
    incluir_bajas: bool = False,
    usuario: Usuario = Depends(lectura),
    db: Session = Depends(get_db),
):
    """Un cliente ve solo los suyos; operador y servicio, los de cualquier cliente."""
    cliente_id, _ = filtro_propio(usuario, cliente_id, None)
    return service.listar(db, cliente_id, incluir_bajas)


@router.get("/{metodo_id}", response_model=MetodoPago)
def obtener_metodo_pago(metodo_id: UUID, usuario: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    metodo = service.buscar(db, metodo_id)
    verificar_cliente(usuario, metodo.cliente_id)
    return MetodoPago.model_validate(metodo)


@router.delete("/{metodo_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_metodo_pago(metodo_id: UUID, usuario: Usuario = Depends(escritura), db: Session = Depends(get_db)):
    """Baja lógica. Repetirla no es un error."""
    metodo = service.buscar(db, metodo_id)
    verificar_cliente(usuario, metodo.cliente_id)
    service.dar_de_baja(db, metodo)
