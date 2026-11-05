import hmac
from typing import Callable, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import NoAutenticadoError, SinPermisoError
from app.security.keycloak import decodificar_y_validar_token
from app.security.models import TokenPayload

oauth2_scheme = HTTPBearer(auto_error=False)

# Token ficticio para desarrollo local y tests cuando AUTH_DISABLED=True
MOCK_DEV_TOKEN = TokenPayload(
    sub="dev-mock-actor",
    roles=["admin", "modulo", "cliente", "conductor"],
    scopes=[
        "tarifas:read",
        "tarifas:write",
        "pagos:read",
        "pagos:write",
        "liquidaciones:read",
        "liquidaciones:write",
    ],
    client_id="m7-mock-client",
    username="dev-admin",
    email="dev@example.com",
    es_servicio=True,
    raw_payload={"mock": True},
)


def requerir_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
) -> TokenPayload:
    """
    Dependencia FastAPI que extrae y valida el token Bearer JWT.
    En modo AUTH_DISABLED=True retorna un token de mock con todos los permisos.
    """
    if settings.AUTH_DISABLED:
        return MOCK_DEV_TOKEN

    if not credentials or not credentials.credentials:
        raise NoAutenticadoError("Encabezado de autorización ausente o no es Bearer")

    return decodificar_y_validar_token(credentials.credentials)


def requerir_permiso(scope_requerido: str) -> Callable[[TokenPayload], TokenPayload]:
    """
    Factory de dependencias FastAPI para requerir un scope específico del contrato OAuth2.
    Ejemplo de uso:
        dependencies=[Depends(requerir_permiso("tarifas:read"))]
    """

    def _verificar_scope(
        token: TokenPayload = Depends(requerir_token),
    ) -> TokenPayload:
        if settings.AUTH_DISABLED:
            return token

        if not token.tiene_scope(scope_requerido):
            raise SinPermisoError(
                f"Permiso insuficiente. Se requiere el scope '{scope_requerido}'"
            )
        return token

    return _verificar_scope


def validar_acceso_recurso(token: TokenPayload, recurso_id: str) -> None:
    """
    Regla RF-1.3 del contrato:
    - Un CLIENTE solo puede ver sus propios pagos (cliente_id).
    - Un CONDUCTOR solo sus propias liquidaciones (conductor_id).
    - Módulos del sistema (Client Credentials) y operadores/administradores
      tienen acceso a recursos de cualquier usuario.
    """
    if settings.AUTH_DISABLED:
        return

    # Si es un módulo del sistema o tiene roles administrativos, se permite el acceso
    if token.es_servicio or token.tiene_rol("admin") or token.tiene_rol("operador"):
        return

    # Si es una persona (cliente o conductor), su sub debe coincidir con el recurso
    if token.sub != recurso_id:
        raise SinPermisoError("No tiene permiso para acceder a recursos de otro usuario")


def validar_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
) -> bool:
    """
    Dependencia para endpoints que no usan Bearer token (ej. Webhook pasarela de pagos),
    sino que autentican mediante el encabezado X-Webhook-Secret.
    """
    if settings.AUTH_DISABLED:
        return True

    if not settings.PASARELA_WEBHOOK_SECRET:
        raise SinPermisoError("Secreto de webhook no configurado en el servidor")

    if not x_webhook_secret or not hmac.compare_digest(
        x_webhook_secret, settings.PASARELA_WEBHOOK_SECRET
    ):
        raise SinPermisoError("Secreto de webhook inválido o ausente")

    return True
