from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.pagos import (
    EstadoPago,
    MetodoPago,
    Pago,
    PagoCreate,
    Reembolso,
    ReembolsoCreate,
    WebhookPasarela,
)
from app.services import store

ESTADOS_COBRADOS = {EstadoPago.aprobado, EstadoPago.reembolsado_parcial}


def crear_pago(datos: PagoCreate, idempotency_key: str | None) -> tuple[Pago, bool]:
    """Devuelve el pago y si fue creado (False si se repitió la Idempotency-Key)."""
    if idempotency_key and idempotency_key in store.idempotencia_pagos:
        return store.pagos[store.idempotencia_pagos[idempotency_key]], False

    ahora = datetime.now(timezone.utc)
    # El efectivo se da por cobrado; el resto queda pendiente hasta que la
    # pasarela confirme por webhook.
    estado = EstadoPago.aprobado if datos.metodo == MetodoPago.efectivo else EstadoPago.pendiente
    pago = Pago(id=uuid4(), estado=estado, creado_en=ahora, actualizado_en=ahora, **datos.model_dump())
    store.pagos[pago.id] = pago
    if idempotency_key:
        store.idempotencia_pagos[idempotency_key] = pago.id
    # TODO: iniciar el cobro en la pasarela externa y guardar referencia_externa
    return pago, True


def obtener_pago(pago_id: UUID) -> Pago:
    pago = store.pagos.get(pago_id)
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    return pago


def listar_pagos(
    viaje_id: UUID | None,
    cliente_id: UUID | None,
    beneficiario_id: UUID | None,
    estado: EstadoPago | None,
) -> list[Pago]:
    return [
        p
        for p in store.pagos.values()
        if (viaje_id is None or p.viaje_id == viaje_id)
        and (cliente_id is None or p.cliente_id == cliente_id)
        and (beneficiario_id is None or p.beneficiario_id == beneficiario_id)
        and (estado is None or p.estado == estado)
    ]


def reembolsar(pago_id: UUID, datos: ReembolsoCreate) -> Reembolso:
    pago = obtener_pago(pago_id)
    if pago.estado not in ESTADOS_COBRADOS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"No se puede reembolsar un pago en estado '{pago.estado.value}'")
    disponible = pago.monto - pago.monto_reembolsado
    monto = datos.monto if datos.monto is not None else disponible
    if monto > disponible:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"El monto supera lo reembolsable ({disponible})")

    ahora = datetime.now(timezone.utc)
    reembolsado = pago.monto_reembolsado + monto
    estado = EstadoPago.reembolsado if reembolsado == pago.monto else EstadoPago.reembolsado_parcial
    store.pagos[pago.id] = pago.model_copy(
        update={"monto_reembolsado": reembolsado, "estado": estado, "actualizado_en": ahora}
    )
    reembolso = Reembolso(id=uuid4(), pago_id=pago.id, monto=monto, motivo=datos.motivo, creado_en=ahora)
    store.reembolsos.setdefault(pago.id, []).append(reembolso)
    return reembolso


def listar_reembolsos(pago_id: UUID) -> list[Reembolso]:
    obtener_pago(pago_id)
    return store.reembolsos.get(pago_id, [])


def procesar_webhook(evento: WebhookPasarela) -> Pago:
    pago = obtener_pago(evento.pago_id)
    if pago.estado != EstadoPago.pendiente:
        # Las pasarelas reintentan: un evento repetido no es un error
        return pago
    if evento.estado not in {EstadoPago.aprobado, EstadoPago.rechazado}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Estado de webhook no válido")
    pago = pago.model_copy(
        update={
            "estado": evento.estado,
            "referencia_externa": evento.referencia_externa,
            "actualizado_en": datetime.now(timezone.utc),
        }
    )
    store.pagos[pago.id] = pago
    return pago
