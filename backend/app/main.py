import uuid
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import get_db

from app.api.v1.router import api_router
from app.core.config import settings

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

app.include_router(api_router)


@app.middleware("http")
async def request_id_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", "").strip()
    if not (1 <= len(request_id) <= 128) or not all(c.isalnum() or c in "._-" for c in request_id):
        request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def problem_response(status: int, title: str, detail: str, request: Request, problem_type: str = "about:blank"):
    return JSONResponse(
        status_code=status,
        content={
            "type": problem_type,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return problem_response(422, "Entidad no procesable", "El cuerpo o los parametros de la solicitud son invalidos", request)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    titles = {
        400: "Solicitud invalida",
        401: "No autenticado",
        403: "Sin permiso",
        404: "No encontrado",
        409: "Conflicto",
        422: "Entidad no procesable",
        500: "Error interno",
        503: "Servicio no disponible",
    }
    detail = exc.detail if isinstance(exc.detail, str) else "La solicitud no pudo completarse"
    return problem_response(exc.status_code, titles.get(exc.status_code, "Error de solicitud"), detail, request)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "type": "about:blank",
                "title": "Servicio no disponible",
                "status": 503,
                "detail": "La base de datos no está disponible",
                "instance": "/health",
            },
        )
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
