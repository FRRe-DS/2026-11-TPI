from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_pre_ping: si MySQL cerró una conexión vieja, la detecta y abre otra
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Abre una sesión por pedido HTTP y la cierra al terminar."""
    with SessionLocal() as db:
        yield db