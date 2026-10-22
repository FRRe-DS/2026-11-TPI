import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    CLIENTE,
    OPERADOR,
    SERVICIO,
    Usuario,
    filtro_propio,
    require_scope,
    verificar_cliente,
    verificar_pago_visible,
)
from app.db.session import get_db
from app.schemas.pagos import (
    CapturaRequest,
    EstadoPago,
    Pago,
    PagoCreate,
    Reembolso,
    ReembolsoCreate,
    TipoOperacion,
    WebhookPasarela,
)
from app.services import pagos as service
from app.services.integraciones import ReservasM9, obtener_m9
from app.services.pasarela import PasarelaPagos, obtener_pasarela

router = APIRouter(prefix="/pagos", tags=["Pagos"])
lectura = require_scope("pagos:read")
flujo = require_scope("pagos:write", SERVICIO, OPERADOR)

IdempotencyKey = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=255)


@router.post("", response_model=Pago, status_code=status.HTTP_201_CREATED)
def autorizar_pago(
    datos: PagoCreate,
    response: Response,
    idempotency_key: str | None = IdempotencyKey,
    usuario: Usuario = Depends(require_scope("pagos:write", CLIENTE, SERVICIO, OPERADOR)),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
    m9: ReservasM9 | None = Depends(obtener_m9),
):
    """Crea el cobro del viaje y lo autoriza en la pasarela (al asignarse el viaje).

    Reenviar la misma Idempotency-Key con el mismo cuerpo devuelve el pago original (200).
    Un segundo cobro vigente para el mismo viaje responde 409.
    """
    verificar_cliente(usuario, datos.cliente_id)
    pago, creado = service.autorizar(db, datos, idempotency_key, usuario, pasarela, m9)
    response.headers["Location"] = f"/api/v1/pagos/{pago.id}"
    if not creado:
        response.status_code = status.HTTP_200_OK
    return pago


@router.get("", response_model=list[Pago])
def listar_pagos(
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    beneficiario_id: UUID | None = None,
    estado: EstadoPago | None = None,
    tipo_operacion: TipoOperacion | None = None,
    usuario: Usuario = Depends(lectura),
    db: Session = Depends(get_db),
):
    """Cada cliente ve solo sus pagos y cada conductor los que lo tienen de beneficiario."""
    cliente_id, beneficiario_id = filtro_propio(usuario, cliente_id, beneficiario_id)
    return service.listar(db, viaje_id, cliente_id, beneficiario_id, estado, tipo_operacion)


@router.get("/{pago_id}", response_model=Pago)
def obtener_pago(pago_id: UUID, usuario: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    pago = service.obtener(db, pago_id)
    verificar_pago_visible(usuario, pago.cliente_id, pago.beneficiario_id)
    return pago


@router.post("/{pago_id}/captura", response_model=Pago)
def capturar_pago(
    pago_id: UUID,
    datos: CapturaRequest | None = None,
    usuario: Usuario = Depends(flujo),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
):
    """Cobra lo autorizado al finalizar el viaje. Sin monto, usa la tarifa final del viaje."""
    return service.capturar(db, pago_id, datos or CapturaRequest(), usuario, pasarela)


@router.post("/{pago_id}/anulacion", response_model=Pago)
def anular_pago(
    pago_id: UUID,
    usuario: Usuario = Depends(flujo),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
):
    """Libera una autorización que no se va a capturar."""
    return service.anular(db, pago_id, usuario.sub, pasarela)


@router.post("/{pago_id}/reembolsos", response_model=Reembolso, status_code=status.HTTP_201_CREATED)
def reembolsar_pago(
    pago_id: UUID,
    datos: ReembolsoCreate,
    response: Response,
    idempotency_key: str | None = IdempotencyKey,
    usuario: Usuario = Depends(flujo),
    db: Session = Depends(get_db),
    pasarela: PasarelaPagos = Depends(obtener_pasarela),
):
    """Reembolso total o parcial. Acepta Idempotency-Key con la misma semántica que el cobro."""
    reembolso, creado = service.reembolsar(db, pago_id, datos, idempotency_key, usuario, pasarela)
    if not creado:
        response.status_code = status.HTTP_200_OK
    return reembolso


@router.get("/{pago_id}/reembolsos", response_model=list[Reembolso])
def listar_reembolsos(pago_id: UUID, usuario: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    pago = service.obtener(db, pago_id)
    verificar_pago_visible(usuario, pago.cliente_id, pago.beneficiario_id)
    return service.listar_reembolsos(db, pago_id)


@router.post("/webhooks/pasarela", response_model=Pago)
def webhook_pasarela(
    evento: WebhookPasarela,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Notificación de la pasarela externa. Se autentica con secreto compartido, no con JWT."""
    esperado = settings.pasarela_webhook_secret
    if not esperado or not x_webhook_secret or not secrets.compare_digest(x_webhook_secret, esperado):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma de webhook inválida")
    return service.procesar_webhook(db, evento)
