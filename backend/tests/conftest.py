from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import store

WEBHOOK_SECRET = "secreto-test"


@pytest.fixture(autouse=True)
def store_limpio():
    """Cada test arranca con el almacenamiento en memoria vacío y las reglas iniciales."""
    for datos in (
        store.reglas,
        store.tarifas_finales,
        store.pagos,
        store.reembolsos,
        store.idempotencia_pagos,
        store.liquidaciones,
    ):
        datos.clear()
    store._seed_reglas()


@pytest.fixture
def client(monkeypatch):
    """Cliente HTTP sin validación de tokens (los scopes se prueban en test_security.py)."""
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "pasarela_webhook_secret", WEBHOOK_SECRET)
    return TestClient(app)


@pytest.fixture
def hoy() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def nuevo_pago(client, monto="1000", metodo="efectivo", beneficiario_id=None, cliente_id=None, headers=None):
    respuesta = client.post(
        "/api/v1/pagos",
        json={
            "viaje_id": str(uuid4()),
            "cliente_id": str(cliente_id or uuid4()),
            "beneficiario_id": str(beneficiario_id or uuid4()),
            "monto": monto,
            "metodo": metodo,
        },
        headers=headers or {},
    )
    assert respuesta.status_code in (200, 201), respuesta.text
    return respuesta.json()
