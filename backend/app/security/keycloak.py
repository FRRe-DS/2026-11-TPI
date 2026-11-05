from typing import Any, Dict, Optional
import jwt
from jwt import PyJWKClient, PyJWKClientError

from app.core.config import settings
from app.core.errors import NoAutenticadoError
from app.security.models import TokenPayload


class KeycloakVerifier:
    """Validador de tokens JWT emitidos por Keycloak usando claves públicas JWKS."""

    def __init__(self, issuer_uri: Optional[str] = None):
        self._issuer_uri = issuer_uri or settings.KEYCLOAK_ISSUER_URI
        self._jwks_client: Optional[PyJWKClient] = None

    @property
    def jwks_url(self) -> str:
        uri = self._issuer_uri.rstrip("/")
        return f"{uri}/protocol/openid-connect/certs"

    def _get_jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                self.jwks_url,
                cache_keys=True,
                max_cached_keys=16,
            )
        return self._jwks_client

    def decodificar_token(self, token: str) -> TokenPayload:
        """
        Descarga (o recupera de caché) la clave pública RS256,
        valida la firma y tiempo de expiración del token y retorna el payload.
        """
        try:
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload: Dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            return TokenPayload.from_dict(payload)

        except jwt.ExpiredSignatureError as exc:
            raise NoAutenticadoError("El token ha expirado") from exc

        except (jwt.InvalidTokenError, PyJWKClientError) as exc:
            raise NoAutenticadoError(f"Token inválido: {exc}") from exc

        except Exception as exc:
            raise NoAutenticadoError(f"Error al verificar autenticación: {exc}") from exc


_verifier: Optional[KeycloakVerifier] = None


def get_keycloak_verifier() -> KeycloakVerifier:
    global _verifier
    if _verifier is None:
        _verifier = KeycloakVerifier()
    return _verifier


def decodificar_y_validar_token(token: str) -> TokenPayload:
    """Función de conveniencia para decodificar un token con el verificador configurado."""
    return get_keycloak_verifier().decodificar_token(token)
