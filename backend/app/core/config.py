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
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{DB_HOST}:{DB_PORT}/{MYSQL_DATABASE}",
    )

    # Configuración de Redis (Caché en memoria - RNF-11)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD", None) or None
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    REDIS_CACHE_TTL_SEGUNDOS: int = int(os.getenv("REDIS_CACHE_TTL_SEGUNDOS", "3600"))

    # Keycloak / Seguridad
    AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "true").lower() == "true"
    KC_PASSWORD: str = os.getenv("KC_PASSWORD", "")
    M7_CLIENT_SECRET: str = os.getenv("M7_CLIENT_SECRET", "")


settings = Settings()
