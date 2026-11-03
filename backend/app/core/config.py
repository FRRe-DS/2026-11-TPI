import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "M7 - Tarifas, Pagos y Liquidaciones"
    VERSION: str = "1.0.0"

    # Configuración de base de datos MySQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "m7")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "admin")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "m7")

    # Keycloak / Seguridad
    AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "true").lower() == "true"
    KC_PASSWORD: str = os.getenv("KC_PASSWORD", "")
    M7_CLIENT_SECRET: str = os.getenv("M7_CLIENT_SECRET", "")


settings = Settings()
