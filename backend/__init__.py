import sys
from pathlib import Path

# Agregar backend al sys.path automáticamente al importar el paquete
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
