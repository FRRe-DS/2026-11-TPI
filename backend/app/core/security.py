"""Autenticación con JWT de Keycloak (M1) y autorización por scope, rol y propiedad.

Roles (realm_access.roles, sin distinguir mayúsculas para convivir con el
contrato de M2, que los escribe en mayúsculas):
- cliente: opera solo sobre sus pagos, métodos de pago y cancelaciones.
- conductor: ve solo sus liquidaciones, saldos y los pagos que lo tienen de beneficiario.
- operador: ve todo; es el único que administra reglas de tarifa y confirma o anula liquidaciones.
- servicio: cuenta de servicio de otro módulo (M5, M6, M9); ve todo y ejecuta los pasos del flujo.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

CLIENTE = "cliente"
CONDUCTOR = "conductor"
OPERADOR = "operador"
SERVICIO = "servicio"
ROLES = {CLIENTE, CONDUCTOR, OPERADOR, SERVICIO}

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Usuario:
    sub: str
    roles: frozenset[str]
    scopes: frozenset[str]

    @property
    def id(self) -> UUID | None:
        """El sub como UUID (en Keycloak, el id del usuario)."""
        try:
            return UUID(self.sub)
        except ValueError:
            return None

    def tiene_rol(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))

    @property
    def ve_todo(self) -> bool:
        return self.tiene_rol(OPERADOR, SERVICIO)


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"})


def sin_permiso(detalle: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detalle)


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(settings.jwks_uri)


def usuario_desde_claims(claims: dict) -> Usuario:
    roles = {r.lower() for r in claims.get("realm_access", {}).get("roles", [])} & ROLES
    return Usuario(
        sub=str(claims.get("sub", "")),
        roles=frozenset(roles),
        scopes=frozenset(claims.get("scope", "").split()),
    )


def get_usuario(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Usuario:
    if settings.auth_disabled:
        return Usuario(sub="dev", roles=frozenset({OPERADOR}), scopes=frozenset({"*"}))
    if credentials is None:
        raise _no_autenticado("Falta el token Bearer")
    try:
        key = _jwks_client().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer_uri,
            audience=settings.keycloak_audience,
            options={"require": ["exp", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _no_autenticado(f"Token inválido: {exc}") from exc
    return usuario_desde_claims(claims)


def require_scope(scope: str, *roles: str):
    """Dependencia que exige el scope y, si se indican, alguno de los roles."""

    def checker(usuario: Usuario = Depends(get_usuario)) -> Usuario:
        if "*" not in usuario.scopes and scope not in usuario.scopes:
            raise sin_permiso(f"Se requiere el scope '{scope}'")
        if roles and not usuario.tiene_rol(*roles):
            raise sin_permiso(f"La operación requiere el rol {' o '.join(roles)}")
        return usuario

    return checker


def verificar_cliente(usuario: Usuario, cliente_id: UUID) -> None:
    """Un cliente solo opera sobre sí mismo; operador y servicio, sobre cualquiera."""
    if usuario.ve_todo:
        return
    if usuario.tiene_rol(CLIENTE) and usuario.id == cliente_id:
        return
    raise sin_permiso("Solo se puede operar sobre los datos del propio cliente")


def verificar_beneficiario(usuario: Usuario, beneficiario_id: UUID) -> None:
    """Un conductor solo ve lo propio; operador y servicio, todo."""
    if usuario.ve_todo:
        return
    if usuario.tiene_rol(CONDUCTOR) and usuario.id == beneficiario_id:
        return
    raise sin_permiso("Solo se pueden consultar las liquidaciones y saldos propios")


def verificar_pago_visible(usuario: Usuario, cliente_id: UUID, beneficiario_id: UUID) -> None:
    """El pago lo ven su cliente, su beneficiario, el operador y los servicios."""
    if usuario.ve_todo:
        return
    if usuario.tiene_rol(CLIENTE) and usuario.id == cliente_id:
        return
    if usuario.tiene_rol(CONDUCTOR) and usuario.id == beneficiario_id:
        return
    raise sin_permiso("El pago no pertenece al usuario")


def filtro_propio(usuario: Usuario, cliente_id: UUID | None, beneficiario_id: UUID | None) -> tuple:
    """Ajusta los filtros de un listado para que cada rol vea solo lo suyo.

    Devuelve (cliente_id, beneficiario_id). Si el filtro pedido apunta a otro
    usuario, responde 403 en lugar de devolver una lista vacía.
    """
    if usuario.ve_todo:
        return cliente_id, beneficiario_id
    if usuario.tiene_rol(CLIENTE):
        if cliente_id not in (None, usuario.id):
            raise sin_permiso("Solo se pueden consultar los datos del propio cliente")
        return usuario.id, beneficiario_id
    if usuario.tiene_rol(CONDUCTOR):
        if beneficiario_id not in (None, usuario.id):
            raise sin_permiso("Solo se pueden consultar los datos propios")
        return cliente_id, usuario.id
    raise sin_permiso("El token no tiene un rol habilitado")
