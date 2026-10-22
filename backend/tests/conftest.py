"""Fixtures comunes: tokens JWT firmados con un par de claves RSA propio, sin Keycloak."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

# La API usa DATABASE_URL; en los tests se apunta a una base descartable.
# Debe definirse antes de importar app.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

from app.core import security  # noqa: E402
from app.core.config import settings  # noqa: E402

TODOS_LOS_SCOPES = (
    "tarifas:read tarifas:write pagos:read pagos:write liquidaciones:read liquidaciones:write"
)


class _ClaveFirma:
    def __init__(self, clave_publica):
        self.key = clave_publica


class JWKSFalso:
    """Reemplaza al PyJWKClient: devuelve siempre la clave pública del fixture."""

    def __init__(self, clave_publica):
        self.clave_publica = clave_publica

    def get_signing_key_from_jwt(self, token: str):
        jwt.get_unverified_header(token)  # un token malformado falla igual que con el cliente real
        return _ClaveFirma(self.clave_publica)


@pytest.fixture(scope="session")
def clave_privada():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def auth_con_claves_de_prueba(monkeypatch, clave_privada):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(security, "_jwks_client", lambda: JWKSFalso(clave_privada.public_key()))


@pytest.fixture
def emitir_token(clave_privada):
    """Firma un JWT como lo haría Keycloak. Permite alterar cualquier claim para probar rechazos."""

    def _emitir(
        sub: str | None = None,
        roles: tuple[str, ...] = ("cliente",),
        scopes: str = TODOS_LOS_SCOPES,
        aud: str | None = None,
        iss: str | None = None,
        vence_en: timedelta = timedelta(minutes=5),
        clave=None,
    ) -> str:
        ahora = datetime.now(timezone.utc)
        claims = {
            "sub": sub or str(uuid4()),
            "iss": iss or settings.keycloak_issuer_uri,
            "aud": aud or settings.keycloak_audience,
            "iat": ahora,
            "exp": ahora + vence_en,
            "scope": scopes,
            "realm_access": {"roles": list(roles)},
        }
        return jwt.encode(claims, clave or clave_privada, algorithm="RS256")

    return _emitir
