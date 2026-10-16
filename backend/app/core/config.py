from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Issuer que figura en el claim "iss" de los tokens
    keycloak_issuer_uri: str = "http://localhost:8080/realms/ds-2026-realm"
    # URL desde donde la API descarga las claves públicas. Dentro de Docker
    # difiere del issuer (keycloak:8080 vs localhost:8080).
    keycloak_jwks_uri: str | None = None
    # Solo para desarrollo local: omite la validación del token
    auth_disabled: bool = False

    # Secreto compartido con la pasarela para autenticar los webhooks
    pasarela_webhook_secret: str | None = None

    supabase_url: str | None = None
    m4_ubicacion_url: str | None = None
    m6_viajes_url: str | None = None
    m9_reservas_url: str | None = None

    @property
    def jwks_uri(self) -> str:
        return self.keycloak_jwks_uri or f"{self.keycloak_issuer_uri}/protocol/openid-connect/certs"


settings = Settings()
