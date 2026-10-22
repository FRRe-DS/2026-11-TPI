import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_token_claims, require_scope
from app.main import app


@pytest.fixture
def client_con_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    yield TestClient(app)
    app.dependency_overrides.clear()


def con_scopes(scopes: str):
    """Reemplaza la validación del JWT por claims fijos, sin depender de Keycloak."""
    app.dependency_overrides[get_token_claims] = lambda: {"sub": "test", "scope": scopes}


def test_health_no_requiere_token(client_con_auth):
    assert client_con_auth.get("/health").json() == {"status": "ok"}


def test_sin_token_devuelve_401(client_con_auth):
    assert client_con_auth.get("/api/v1/tarifas/reglas").status_code == 401


def test_token_malformado_devuelve_401(client_con_auth):
    respuesta = client_con_auth.get("/api/v1/pagos", headers={"Authorization": "Bearer no-es-un-jwt"})

    assert respuesta.status_code == 401


def test_scope_de_lectura_permite_leer_pero_no_escribir(client_con_auth):
    con_scopes("tarifas:read")

    assert client_con_auth.get("/api/v1/tarifas/reglas").status_code == 200
    respuesta = client_con_auth.post(
        "/api/v1/tarifas/reglas",
        json={
            "tipo_vehiculo": "auto",
            "tarifa_base": "1",
            "precio_por_km": "1",
            "precio_por_minuto": "1",
            "tarifa_minima": "1",
        },
    )
    assert respuesta.status_code == 403


def test_scope_de_un_dominio_no_habilita_otro(client_con_auth):
    con_scopes("tarifas:read tarifas:write")

    assert client_con_auth.get("/api/v1/pagos").status_code == 403
    assert client_con_auth.get("/api/v1/liquidaciones").status_code == 403


def test_require_scope_acepta_el_scope_entre_varios():
    claims = {"scope": "openid pagos:read pagos:write"}

    assert require_scope("pagos:write")(claims) is claims


def test_require_scope_rechaza_si_falta():
    with pytest.raises(HTTPException) as error:
        require_scope("pagos:write")({"scope": "pagos:read"})

    assert error.value.status_code == 403


def test_require_scope_rechaza_token_sin_scopes():
    with pytest.raises(HTTPException):
        require_scope("pagos:read")({})


def test_comodin_habilita_cualquier_scope():
    assert require_scope("liquidaciones:write")({"scope": "*"})


def test_auth_deshabilitada_devuelve_claims_de_desarrollo(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)

    assert get_token_claims(None)["scope"] == "*"
