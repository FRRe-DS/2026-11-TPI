from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    """Representación del payload decodificado de un token JWT de Keycloak."""

    sub: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
    client_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    es_servicio: bool = False
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    def tiene_scope(self, scope: str) -> bool:
        """Verifica si el token cuenta con el scope requerido."""
        return scope in self.scopes

    def tiene_rol(self, rol: str) -> bool:
        """Verifica si el token tiene un rol específico (case-insensitive)."""
        rol_lower = rol.lower()
        return any(r.lower() == rol_lower for r in self.roles)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TokenPayload":
        """Construye un TokenPayload a partir del diccionario decodificado de Keycloak."""
        sub = payload.get("sub")
        username = payload.get("preferred_username")
        email = payload.get("email")
        client_id = payload.get("azp") or payload.get("client_id")

        # 1. Extraer scopes (en Keycloak vienen como string separado por espacios en 'scope')
        raw_scope = payload.get("scope", "")
        if isinstance(raw_scope, str):
            scopes = [s.strip() for s in raw_scope.split() if s.strip()]
        elif isinstance(raw_scope, list):
            scopes = [str(s).strip() for s in raw_scope if str(s).strip()]
        else:
            scopes = []

        # 2. Extraer roles de realm_access y resource_access
        roles: List[str] = []
        realm_access = payload.get("realm_access")
        if isinstance(realm_access, dict):
            roles.extend(realm_access.get("roles", []))

        resource_access = payload.get("resource_access")
        if isinstance(resource_access, dict):
            for res_client, client_data in resource_access.items():
                if isinstance(client_data, dict):
                    roles.extend(client_data.get("roles", []))

        roles_unicos = list(dict.fromkeys(roles))

        # 3. Determinar si es un servicio/módulo (Client Credentials) o una persona
        es_servicio = False
        if username and username.startswith("service-account-"):
            es_servicio = True
        elif not email and not username and client_id:
            es_servicio = True
        elif any(r.upper() in {"SERVICE", "MODULO", "SISTEMA", "ADMIN"} for r in roles_unicos):
            es_servicio = True

        return cls(
            sub=sub,
            roles=roles_unicos,
            scopes=scopes,
            client_id=client_id,
            username=username,
            email=email,
            es_servicio=es_servicio,
            raw_payload=payload,
        )
