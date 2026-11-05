import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "M7 - Tarifas, Pagos y Liquidaciones"
    VERSION: str = "1.0.0"

    # Configuracion de base de datos MySQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "m7")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "admin")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "m7")
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{MYSQL_DATABASE}",
    )

    # Keycloak / Seguridad
    AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "true").lower() == "true"
    KC_PASSWORD: str = os.getenv("KC_PASSWORD", "")
    M7_CLIENT_SECRET: str = os.getenv("M7_CLIENT_SECRET", "")
    KEYCLOAK_ISSUER_URI: str = os.getenv(
        "KEYCLOAK_ISSUER_URI",
        "http://localhost:8080/realms/ds-2026-realm",
    )
    PASARELA_WEBHOOK_SECRET: str = os.getenv("PASARELA_WEBHOOK_SECRET", "")

    # URLs Externas
    M4_UBICACION_URL: str = os.getenv("M4_UBICACION_URL", "")
    M6_VIAJES_URL: str = os.getenv("M6_VIAJES_URL", "")
    M9_RESERVAS_URL: str = os.getenv("M9_RESERVAS_URL", "")
    PASARELA_URL: str = os.getenv("PASARELA_URL", "")

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_EXCHANGE: str = os.getenv("RABBITMQ_EXCHANGE", "transporte")
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")


settings = Settings()
