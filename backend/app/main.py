from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import (
    ServicioNoDisponibleError,
    configurar_manejadores_errores,
    crear_respuesta_problema,
    normalizar_o_generar_request_id,
)
from app.db.session import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Microservicio de Tarifas, Pagos y Liquidaciones (Módulo 7 - TPI 2026)",
)

# 1. Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Middleware para X-Request-Id (RFC y Contrato OpenAPI)
@app.middleware("http")
async def x_request_id_middleware(request: Request, call_next):
    raw_req_id = request.headers.get("X-Request-Id")
    req_id = normalizar_o_generar_request_id(raw_req_id)
    request.state.request_id = req_id

    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


# 3. Middleware de validación de tamaño y tipo de cuerpo (1 MiB y application/json)
LIMITE_CUERPO_BYTES = 1024 * 1024  # 1 MiB


@app.middleware("http")
async def validar_cuerpo_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > LIMITE_CUERPO_BYTES:
            return crear_respuesta_problema(
                request=request,
                status=413,
                title="Cuerpo demasiado grande",
                detail="El cuerpo supera 1 MiB",
            )

        content_type = request.headers.get("content-type", "")
        if content_length and int(content_length) > 0:
            if not content_type.startswith("application/json"):
                return crear_respuesta_problema(
                    request=request,
                    status=415,
                    title="Tipo de contenido no soportado",
                    detail="El Content-Type del cuerpo debe ser application/json",
                )

    return await call_next(request)


# 4. Registrar manejadores de error centralizados (RFC 9457)
configurar_manejadores_errores(app)

# 5. Enrutador principal de la API
app.include_router(api_router)


# 6. Endpoint de Salud
@app.get("/health", tags=["Salud"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServicioNoDisponibleError(detail="La base de datos de M7 no está disponible") from exc
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
