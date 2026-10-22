from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+psycopg://usuario:clave@host:puerto/base
    database_url: str = "postgresql+psycopg://m7:m7@localhost:5432/m7"

    # Issuer que figura en el claim "iss" de los tokens
    keycloak_issuer_uri: str = "http://localhost:8080/realms/ds-2026-realm"
    # URL desde donde la API descarga las claves públicas. Dentro de Docker
    # difiere del issuer (keycloak:8080 vs localhost:8080).
    keycloak_jwks_uri: str | None = None
    # Valor que debe figurar en el claim "aud" de los tokens
    keycloak_audience: str = "m7-tarifas"
    # Solo para desarrollo local: omite la validación del token
    auth_disabled: bool = False

    # Secreto compartido con la pasarela para autenticar los webhooks
    pasarela_webhook_secret: str | None = None
    # Espera máxima por cada llamada a la pasarela (RNF-13)
    pasarela_timeout_s: float = Field(default=3.0, gt=0)

    # Porcentaje que retiene la plataforma en cada liquidación (0.20 = 20 %)
    comision_plataforma: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    # Minutos durante los que una estimación puede usarse para cobrar o reservar
    estimacion_vigencia_min: int = Field(default=15, gt=0)

    # Reglas de cargo de cancelación (RF-7.4), a acordar con el consorcio
    cancelacion_periodo_gracia_min: int = Field(default=5, ge=0)
    cancelacion_cargo_asignado: Decimal = Field(default=Decimal("500"), ge=0)
    cancelacion_cargo_conductor_en_punto: Decimal = Field(default=Decimal("1000"), ge=0)

    m4_ubicacion_url: str | None = None
    m6_viajes_url: str | None = None
    m9_reservas_url: str | None = None
    # Espera por intento y reintentos de las consultas a otros módulos
    integraciones_timeout_s: float = Field(default=2.0, gt=0)
    integraciones_reintentos: int = Field(default=1, ge=0, le=3)

    @property
    def jwks_uri(self) -> str:
        return self.keycloak_jwks_uri or f"{self.keycloak_issuer_uri}/protocol/openid-connect/certs"


settings = Settings()
