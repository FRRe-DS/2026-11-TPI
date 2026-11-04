import sys
from decimal import Decimal
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Asegurar que el directorio backend/ esté en sys.path tanto para ejecución local como pytest
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ParametroTarifa  # noqa: E402

# Base de datos SQLite en memoria para tests rápidos, aislados y reproducibles con SQLAlchemy ORM
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def _seed_tarifas(session) -> None:
    """Inserta los parámetros iniciales de tarifa (auto y moto) equivalentes a init-db/01-init.sql."""
    existentes = session.scalars(select(ParametroTarifa)).all()
    if not existentes:
        session.add_all(
            [
                ParametroTarifa(
                    tipo_vehiculo="auto",
                    base=Decimal("500.00"),
                    por_km=Decimal("150.00"),
                    por_min=Decimal("50.00"),
                    minima=Decimal("800.00"),
                    cargo_cancelacion=Decimal("400.00"),
                    comision_pct=Decimal("15.00"),
                ),
                ParametroTarifa(
                    tipo_vehiculo="moto",
                    base=Decimal("350.00"),
                    por_km=Decimal("100.00"),
                    por_min=Decimal("35.00"),
                    minima=Decimal("500.00"),
                    cargo_cancelacion=Decimal("250.00"),
                    comision_pct=Decimal("12.00"),
                ),
            ]
        )
        session.commit()


@pytest.fixture
def db_session():
    """Crea las tablas del modelo ORM, carga las tarifas semilla y limpia al finalizar cada test."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestingSessionLocal()
    _seed_tarifas(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client(db_session):
    """Fixture que provee un cliente HTTP con la sesión de prueba inyectada vía Depends(get_db)."""
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
