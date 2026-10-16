from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(settings.jwks_uri)


def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if settings.auth_disabled:
        return {"sub": "dev", "scope": "*"}
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token Bearer")
    try:
        key = _jwks_client().get_signing_key_from_jwt(credentials.credentials)
        return jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer_uri,
            # TODO: validar audiencia cuando se definan los clients del realm
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {exc}") from exc


def require_scope(scope: str):
    """Dependencia que exige que el token incluya el scope indicado."""

    def checker(claims: dict = Depends(get_token_claims)) -> dict:
        scopes = claims.get("scope", "").split()
        if "*" not in scopes and scope not in scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Se requiere el scope '{scope}'")
        return claims

    return checker
