from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Las fechas se leen siempre en UTC, sin depender de la zona del servidor de base
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"})
# expire_on_commit: después de cada commit los datos se releen de la base, así una
# respuesta muestra los montos con la escala de NUMERIC y no el valor en memoria
SessionLocal = sessionmaker(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
