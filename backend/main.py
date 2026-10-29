"""
Punto de entrada principal para el backend.
Provee compatibilidad hacia atrás con 'uvicorn main:app --reload' ejecutado desde la carpeta backend/.
La arquitectura modular del microservicio se encuentra organizada dentro del paquete 'app'.
"""
import sys
from pathlib import Path

# Asegurar que el directorio backend/ esté en el PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
