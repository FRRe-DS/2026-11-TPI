import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.core.config import settings
from app.core.security import require_scope
from app.schemas.pagos import EstadoPago, Pago, PagoCreate, Reembolso, ReembolsoCreate, WebhookPasarela
from app.services import pagos as service

router = APIRouter(prefix="/pagos", tags=["Pagos"])
lectura = [Depends(require_scope("pagos:read"))]
escritura = [Depends(require_scope("pagos:write"))]


@router.post("", response_model=Pago, status_code=status.HTTP_201_CREATED, dependencies=escritura)
def crear_pago(
    datos: PagoCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Registra el cobro de un viaje. Reenviar la misma Idempotency-Key devuelve el pago original."""
    pago, creado = service.crear_pago(datos, idempotency_key)
    if not creado:
        response.status_code = status.HTTP_200_OK
    return pago


@router.get("", response_model=list[Pago], dependencies=lectura)
def listar_pagos(
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    beneficiario_id: UUID | None = None,
    estado: EstadoPago | None = None,
):
    return service.listar_pagos(viaje_id, cliente_id, beneficiario_id, estado)


@router.get("/{pago_id}", response_model=Pago, dependencies=lectura)
def obtener_pago(pago_id: UUID):
    return service.obtener_pago(pago_id)


@router.post(
    "/{pago_id}/reembolsos",
    response_model=Reembolso,
    status_code=status.HTTP_201_CREATED,
    dependencies=escritura,
)
def reembolsar_pago(pago_id: UUID, datos: ReembolsoCreate):
    """Reembolso total o parcial (por ejemplo, viaje cancelado en M9 Reservas)."""
    return service.reembolsar(pago_id, datos)


@router.get("/{pago_id}/reembolsos", response_model=list[Reembolso], dependencies=lectura)
def listar_reembolsos(pago_id: UUID):
    return service.listar_reembolsos(pago_id)


@router.post("/webhooks/pasarela", response_model=Pago, include_in_schema=True)
def webhook_pasarela(evento: WebhookPasarela, x_webhook_secret: str | None = Header(default=None)):
    """Notificación de la pasarela externa. Se autentica con secreto compartido, no con JWT."""
    esperado = settings.pasarela_webhook_secret
    if not esperado or not x_webhook_secret or not secrets.compare_digest(x_webhook_secret, esperado):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma de webhook inválida")
    return service.procesar_webhook(evento)
