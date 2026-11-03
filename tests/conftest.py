import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Asegurar que el directorio backend/ esté en sys.path tanto para ejecución local como pytest
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Importar app vía backend.app.main (resuelto directamente por el IDE desde la raíz)
from backend.app.main import app  # noqa: E402


@pytest.fixture
def client():
    """Fixture que provee un cliente HTTP para interactuar con la API en memoria."""
    return TestClient(app)
