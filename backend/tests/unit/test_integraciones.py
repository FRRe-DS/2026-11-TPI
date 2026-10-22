"""Clientes de M4, M6 y M9 contra un transporte simulado de httpx (sin red)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.services.integraciones import (
    ClienteM4,
    ClienteM6,
    ClienteM9,
    DependenciaNoDisponible,
    RecursoExternoInexistente,
    obtener_m4,
    obtener_m6,
    obtener_m9,
)


def transporte(*respuestas):
    """Devuelve las respuestas en orden; una excepción se lanza como error de red."""
    pendientes = list(respuestas)
    pedidos = []

    def manejar(request: httpx.Request):
        pedidos.append(request)
        siguiente = pendientes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    mock = httpx.MockTransport(manejar)
    mock.pedidos = pedidos
    return mock


def test_m4_estima_la_ruta():
    t = transporte(httpx.Response(200, json={"distancia_km": 12.5, "duracion_min": 25}))

    ruta = ClienteM4("http://m4", t).estimar_ruta((-27.45, -58.98), (-27.47, -58.83), "auto")

    assert ruta.distancia_km == Decimal("12.5")
    assert ruta.duracion_min == Decimal("25")
    assert t.pedidos[0].url.path == "/api/v1/rutas/estimacion"
    assert t.pedidos[0].url.params["tipo_vehiculo"] == "auto"


def test_m6_obtiene_el_viaje():
    viaje_id = uuid4()
    t = transporte(
        httpx.Response(200, json={"id": str(viaje_id), "estado": "asignado", "asignado_en": "2026-10-22T12:00:00+00:00"})
    )

    viaje = ClienteM6("http://m6/", t).obtener_viaje(viaje_id)

    assert viaje.estado == "asignado"
    assert viaje.asignado_en == datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
    assert t.pedidos[0].url.path == f"/api/v1/viajes/{viaje_id}"


def test_m9_obtiene_la_reserva():
    reserva_id, cliente_id = uuid4(), uuid4()
    t = transporte(httpx.Response(200, json={"id": str(reserva_id), "cliente_id": str(cliente_id), "estado": "confirmada"}))

    assert ClienteM9("http://m9", t).obtener_reserva(reserva_id).cliente_id == cliente_id


def test_reintenta_una_vez_ante_error_5xx(monkeypatch):
    monkeypatch.setattr(settings, "integraciones_reintentos", 1)
    viaje_id = uuid4()
    t = transporte(httpx.Response(503), httpx.Response(200, json={"id": str(viaje_id), "estado": "solicitado"}))

    assert ClienteM6("http://m6", t).obtener_viaje(viaje_id).estado == "solicitado"
    assert len(t.pedidos) == 2


def test_sin_respuesta_tras_los_reintentos_es_503(monkeypatch):
    monkeypatch.setattr(settings, "integraciones_reintentos", 1)
    t = transporte(httpx.ConnectTimeout("timeout"), httpx.ReadTimeout("timeout"))

    with pytest.raises(DependenciaNoDisponible) as error:
        ClienteM6("http://m6", t).obtener_viaje(uuid4())

    assert error.value.status_code == 503
    assert error.value.headers == {"Retry-After": "5"}
    assert len(t.pedidos) == 2


def test_recurso_inexistente_no_se_reintenta():
    t = transporte(httpx.Response(404))

    with pytest.raises(RecursoExternoInexistente) as error:
        ClienteM9("http://m9", t).obtener_reserva(uuid4())

    assert error.value.status_code == 422
    assert len(t.pedidos) == 1


def test_otro_error_4xx_es_503_sin_reintento():
    t = transporte(httpx.Response(401))

    with pytest.raises(DependenciaNoDisponible):
        ClienteM9("http://m9", t).obtener_reserva(uuid4())
    assert len(t.pedidos) == 1


def test_dependencias_segun_configuracion(monkeypatch):
    for nombre in ("m4_ubicacion_url", "m6_viajes_url", "m9_reservas_url"):
        monkeypatch.setattr(settings, nombre, None)
    assert obtener_m4() is None and obtener_m6() is None and obtener_m9() is None

    monkeypatch.setattr(settings, "m4_ubicacion_url", "http://m4")
    monkeypatch.setattr(settings, "m6_viajes_url", "http://m6")
    monkeypatch.setattr(settings, "m9_reservas_url", "http://m9")
    assert isinstance(obtener_m4(), ClienteM4)
    assert isinstance(obtener_m6(), ClienteM6)
    assert isinstance(obtener_m9(), ClienteM9)
