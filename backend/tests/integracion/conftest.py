"""Tests de integración: API completa contra PostgreSQL real, pasarela simulada y stubs de M4/M6/M9.

Requieren TEST_DATABASE_URL (por ejemplo, el servicio db-test del docker-compose).
"""

import importlib.util
import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, text

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.db import models
from app.db.session import engine
from app.main import app
from app.services.integraciones import (
    RecursoExternoInexistente,
    ReservaExterna,
    RutaEstimada,
    ViajeExterno,
    obtener_m4,
    obtener_m6,
    obtener_m9,
)
from app.services.pasarela import PasarelaSimulada, obtener_pasarela
from tests.conftest import TEST_DATABASE_URL, TODOS_LOS_SCOPES

BACKEND = Path(__file__).resolve().parents[2]
WEBHOOK_SECRET = "secreto-de-prueba"
VISA = "4111111111111111"


def _reglas_iniciales() -> list[dict]:
    """Toma las reglas de la migración de seed para no duplicarlas."""
    ruta = BACKEND / "alembic" / "versions" / "0002_reglas_iniciales.py"
    spec = importlib.util.spec_from_file_location("seed_reglas", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.REGLAS


@pytest.fixture(scope="session")
def base_migrada():
    if not TEST_DATABASE_URL:
        pytest.skip("Definir TEST_DATABASE_URL para correr los tests de integración contra PostgreSQL")
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return _reglas_iniciales()


@pytest.fixture(autouse=True)
def base_limpia(base_migrada):
    """Cada test arranca con las tablas vacías y las reglas iniciales (TRUNCATE no dispara el trigger)."""
    tablas = ", ".join(t.name for t in models.Base.metadata.sorted_tables)
    with engine.begin() as conexion:
        conexion.execute(text(f"TRUNCATE {tablas} CASCADE"))
        conexion.execute(insert(models.ReglaTarifa), base_migrada)


# --- Dobles de prueba -------------------------------------------------------


class PasarelaPrueba(PasarelaSimulada):
    """Pasarela simulada con fallas activables y registro de llamadas."""

    def __init__(self):
        super().__init__(demora_sin_respuesta_s=0.3)
        self.captura_sin_respuesta = False
        self.anulacion_sin_respuesta = False
        self.reembolso_rechazado = False
        self.llamadas: list[str] = []

    def _esperar_si(self, activado: bool):
        if activado:
            time.sleep(self.demora_sin_respuesta_s)

    def autorizar(self, pago_id, monto, token):
        self.llamadas.append("autorizar")
        return super().autorizar(pago_id, monto, token)

    def capturar(self, referencia, monto):
        self.llamadas.append("capturar")
        self._esperar_si(self.captura_sin_respuesta)
        return super().capturar(referencia, monto)

    def anular(self, referencia):
        self.llamadas.append("anular")
        self._esperar_si(self.anulacion_sin_respuesta)
        return super().anular(referencia)

    def reembolsar(self, referencia, monto):
        self.llamadas.append("reembolsar")
        resultado = super().reembolsar(referencia, monto)
        if self.reembolso_rechazado:
            return type(resultado)(False, resultado.referencia, "Reembolso rechazado por el emisor")
        return resultado


class M4Stub:
    def __init__(self):
        self.ruta = RutaEstimada(Decimal("10"), Decimal("20"))
        self.error: Exception | None = None
        self.consultas = 0

    def estimar_ruta(self, origen, destino, tipo_vehiculo):
        self.consultas += 1
        if self.error:
            raise self.error
        return self.ruta


class M6Stub:
    def __init__(self):
        self.viajes: dict[UUID, ViajeExterno] = {}

    def obtener_viaje(self, viaje_id):
        if viaje_id not in self.viajes:
            raise RecursoExternoInexistente("M6 Viajes", f"/api/v1/viajes/{viaje_id}")
        return self.viajes[viaje_id]


class M9Stub:
    def __init__(self):
        self.reservas: dict[UUID, ReservaExterna] = {}
        self.error: Exception | None = None

    def obtener_reserva(self, reserva_id):
        if self.error:
            raise self.error
        if reserva_id not in self.reservas:
            raise RecursoExternoInexistente("M9 Reservas", f"/api/v1/reservas/{reserva_id}")
        return self.reservas[reserva_id]


@pytest.fixture
def pasarela(monkeypatch):
    monkeypatch.setattr(settings, "pasarela_timeout_s", 0.1)
    return PasarelaPrueba()


@pytest.fixture
def m4():
    return M4Stub()


@pytest.fixture
def m6():
    return M6Stub()


@pytest.fixture
def m9():
    return M9Stub()


@pytest.fixture
def integraciones():
    """Por defecto los otros módulos no están configurados (como en local sin URLs)."""
    return {"m4": False, "m6": False, "m9": False}


@pytest.fixture
def client(monkeypatch, pasarela, m4, m6, m9, integraciones):
    monkeypatch.setattr(settings, "pasarela_webhook_secret", WEBHOOK_SECRET)
    app.dependency_overrides[obtener_pasarela] = lambda: pasarela
    app.dependency_overrides[obtener_m4] = lambda: m4 if integraciones["m4"] else None
    app.dependency_overrides[obtener_m6] = lambda: m6 if integraciones["m6"] else None
    app.dependency_overrides[obtener_m9] = lambda: m9 if integraciones["m9"] else None
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Actores ----------------------------------------------------------------


class Actores:
    """Un cliente, un conductor, un operador y un módulo (servicio) con sus tokens."""

    def __init__(self, emitir_token):
        self._emitir = emitir_token
        self.cliente_id = uuid4()
        self.conductor_id = uuid4()

    def headers(self, *roles: str, sub=None, scopes: str = TODOS_LOS_SCOPES, **extra) -> dict:
        token = self._emitir(sub=str(sub or uuid4()), roles=roles, scopes=scopes)
        return {"Authorization": f"Bearer {token}", **extra}

    @property
    def cliente(self) -> dict:
        return self.headers("cliente", sub=self.cliente_id)

    @property
    def conductor(self) -> dict:
        return self.headers("conductor", sub=self.conductor_id)

    @property
    def operador(self) -> dict:
        return self.headers("operador")

    @property
    def servicio(self) -> dict:
        return self.headers("servicio")


@pytest.fixture
def actores(emitir_token) -> Actores:
    return Actores(emitir_token)


# --- Ayudantes del flujo ----------------------------------------------------


def registrar_tarjeta(client, actores, numero=VISA, cliente_id=None) -> dict:
    respuesta = client.post(
        "/api/v1/metodos-pago",
        json={"cliente_id": str(cliente_id or actores.cliente_id), "tipo": "tarjeta", "numero_tarjeta": numero},
        headers=actores.operador,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def autorizar(client, actores, metodo_id=None, headers=None, viaje_id=None, **extra):
    cuerpo = {
        "viaje_id": str(viaje_id or uuid4()),
        "cliente_id": str(actores.cliente_id),
        "beneficiario_id": str(actores.conductor_id),
        "monto": "5000",
        **extra,
    }
    if metodo_id:
        cuerpo["metodo_pago_id"] = metodo_id
    return client.post("/api/v1/pagos", json=cuerpo, headers=headers or actores.servicio)


def pago_capturado(client, actores, monto="5000", con_tarjeta=False) -> dict:
    metodo_id = registrar_tarjeta(client, actores)["id"] if con_tarjeta else None
    pago = autorizar(client, actores, metodo_id, monto=monto).json()
    respuesta = client.post(f"/api/v1/pagos/{pago['id']}/captura", json={}, headers=actores.servicio)
    assert respuesta.json()["estado"] == "capturado", respuesta.text
    return respuesta.json()


def ejecutar_sql(sql: str, **parametros):
    with engine.begin() as conexion:
        return conexion.execute(text(sql), parametros)
