import json
import logging
import re
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import error_interno, registrar_manejadores
from app.db.session import get_db
from app.routers import cancelaciones, liquidaciones, metodos_pago, movimientos, pagos, tarifas

REQUEST_ID_VALIDO = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("m7.http")

app = FastAPI(
    title="M7 - Tarifas, Pagos y Liquidaciones",
    description="Microservicio del Grupo 11 - TPI Desarrollo de Software 2026",
    version="0.2.0",
)
registrar_manejadores(app)

for router in (
    tarifas.router,
    pagos.router,
    metodos_pago.router,
    cancelaciones.router,
    liquidaciones.router,
    movimientos.router,
):
    app.include_router(router, prefix="/api/v1")


@app.middleware("http")
async def correlacion(request: Request, call_next):
    """Propaga X-Request-Id (o genera uno) y deja un log estructurado por solicitud (RNF-14)."""
    recibido = request.headers.get("X-Request-Id", "")
    request_id = recibido if REQUEST_ID_VALIDO.match(recibido) else uuid4().hex
    request.state.request_id = request_id
    inicio = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - toda falla no controlada sale como problem+json
        response = error_interno(request, exc)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "metodo": request.method,
                # Solo la ruta: los parámetros de consulta pueden tener datos personales (RNF-19)
                "ruta": request.url.path,
                "estado": response.status_code,
                "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
            }
        )
    )
    return response


@app.get("/health", tags=["Salud"])
def health(db: Session = Depends(get_db)):
    """Responde 200 si el servicio y su base están disponibles; si no, 503."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La base de datos no está disponible") from exc
    return {"estado": "ok"}
