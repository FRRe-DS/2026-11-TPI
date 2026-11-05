from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import ping_redis
from app.db.session import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Microservicio de Tarifas, Pagos y Liquidaciones (Módulo 7 - TPI 2026)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Manejador global de errores de base de datos para no devolver 500 genérico."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "DATABASE_UNAVAILABLE",
            "detail": "No se pudo conectar a la base de datos MySQL. Asegúrate de que el contenedor de base de datos esté corriendo ('docker compose up -d db').",
            "mensaje_tecnico": str(exc.orig) if hasattr(exc, "orig") else str(exc),
        },
    )


app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "La base de datos no está disponible") from exc

    redis_status = "disabled"
    if settings.REDIS_ENABLED:
        redis_status = "connected" if ping_redis() else "unavailable"

    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "database": "connected",
        "redis": redis_status,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
