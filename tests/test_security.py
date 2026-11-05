import time
import jwt
from unittest.mock import MagicMock, patch
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.core.errors import NoAutenticadoError, SinPermisoError
from app.security.dependencies import (
    MOCK_DEV_TOKEN,
    requerir_permiso,
    requerir_token,
    validar_acceso_recurso,
    validar_webhook_secret,
)
from app.security.models import TokenPayload
from app.security.keycloak import KeycloakVerifier


# ============================================================================
# 1. Pruebas con AUTH_DISABLED = True (Modo Desarrollo)
# ============================================================================

def test_auth_disabled_retorna_mock_token():
    """Con AUTH_DISABLED=True, requerir_token debe devolver el token mock sin pedir credenciales."""
    with patch.object(settings, "AUTH_DISABLED", True):
        token = requerir_token(None)
        assert token == MOCK_DEV_TOKEN
        assert token.tiene_scope("tarifas:read")
        assert token.tiene_scope("pagos:write")
        assert token.es_servicio is True


def test_auth_disabled_permite_cualquier_scope():
    """Con AUTH_DISABLED=True, cualquier verificación de scope es aprobada."""
    with patch.object(settings, "AUTH_DISABLED", True):
        dep = requerir_permiso("scope:inexistente")
        token = dep(MOCK_DEV_TOKEN)
        assert token is not None


def test_auth_disabled_permite_acceso_recurso():
    """Con AUTH_DISABLED=True, no se bloquea el acceso a recursos ajenos."""
    with patch.object(settings, "AUTH_DISABLED", True):
        # No debe lanzar ninguna excepción aunque los IDs no coincidan
        validar_acceso_recurso(MOCK_DEV_TOKEN, "cualquier-otro-usuario")


# ============================================================================
# 2. Pruebas con AUTH_DISABLED = False (Modo Producción con Keycloak)
# ============================================================================

def test_auth_enabled_sin_token_falla():
    """Sin token Bearer, debe responder con 401 (NoAutenticadoError)."""
    with patch.object(settings, "AUTH_DISABLED", False):
        with pytest.raises(NoAutenticadoError) as exc_info:
            requerir_token(None)
        assert exc_info.value.status_code == 401


def test_verificacion_de_scopes():
    """Si el token no contiene el scope solicitado, debe lanzar 403 (SinPermisoError)."""
    with patch.object(settings, "AUTH_DISABLED", False):
        token_limitado = TokenPayload(
            sub="usr-123",
            scopes=["tarifas:read"],
            roles=["cliente"],
            es_servicio=False,
        )

        dep_tarifas = requerir_permiso("tarifas:read")
        assert dep_tarifas(token_limitado) == token_limitado

        dep_pagos = requerir_permiso("pagos:write")
        with pytest.raises(SinPermisoError) as exc_info:
            dep_pagos(token_limitado)
        assert exc_info.value.status_code == 403


def test_regla_privacidad_rf_1_3_cliente():
    """Un cliente solo puede acceder a sus propios recursos."""
    with patch.object(settings, "AUTH_DISABLED", False):
        token_cliente = TokenPayload(
            sub="cliente-juan",
            roles=["cliente"],
            scopes=["pagos:read"],
            es_servicio=False,
        )

        # Puede ver sus propios datos
        validar_acceso_recurso(token_cliente, "cliente-juan")

        # No puede ver datos de pedro (debe lanzar 403)
        with pytest.raises(SinPermisoError) as exc_info:
            validar_acceso_recurso(token_cliente, "cliente-pedro")
        assert exc_info.value.status_code == 403


def test_regla_privacidad_rf_1_3_servicio_tiene_acceso_total():
    """Los módulos del sistema (M5, M6, M9) pueden consultar recursos de cualquier usuario."""
    with patch.object(settings, "AUTH_DISABLED", False):
        token_servicio = TokenPayload(
            sub="service-account-m6",
            roles=["modulo"],
            scopes=["pagos:read", "pagos:write"],
            es_servicio=True,
        )

        validar_acceso_recurso(token_servicio, "cliente-cualquiera")


# ============================================================================
# 3. Pruebas de Firma Criptográfica JWT y Expiración (RS256)
# ============================================================================

def test_verificacion_token_expirado():
    """Un token vencido debe ser rechazado con 401."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    token_vencido = jwt.encode(
        {"sub": "usr-1", "exp": int(time.time()) - 100},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-id"},
    )

    verifier = KeycloakVerifier()
    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
    verifier._jwks_client = mock_jwk_client

    with pytest.raises(NoAutenticadoError) as exc_info:
        verifier.decodificar_token(token_vencido)
    assert exc_info.value.status_code == 401
    assert "expirado" in str(exc_info.value.detail).lower()


# ============================================================================
# 4. Pruebas de Webhook Secret
# ============================================================================

def test_webhook_secret_valido():
    with patch.object(settings, "AUTH_DISABLED", False):
        with patch.object(settings, "PASARELA_WEBHOOK_SECRET", "mi_secreto_super_seguro"):
            assert validar_webhook_secret("mi_secreto_super_seguro") is True

            with pytest.raises(SinPermisoError):
                validar_webhook_secret("secreto_equivocado")
