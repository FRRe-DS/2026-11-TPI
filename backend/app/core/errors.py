"""
Manejo centralizado de errores según el contrato OpenAPI y RFC 9457 (Problem Details).
Convenciones del contrato M7:
- Formato: application/problem+json
- Encabezado obligatorio en toda respuesta: X-Request-Id (formato: ^[A-Za-z0-9._-]{1,128}$)
- Errores genéricos: type: about:blank con títulos estándar en español.
- Errores de dominio: type propio (/errores/...).
"""
import re
import uuid
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

X_REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
MEDIA_TYPE_PROBLEM = "application/problem+json"


def normalizar_o_generar_request_id(valor: Optional[str]) -> str:
    """Valida el X-Request-Id recibido o genera uno nuevo si no cumple el formato."""
    if valor and X_REQUEST_ID_REGEX.match(valor):
        return valor
    return str(uuid.uuid4())


def obtener_request_id(request: Request) -> str:
    """Recupera el request_id del estado de la solicitud o del encabezado."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    req_id = normalizar_o_generar_request_id(request.headers.get("X-Request-Id"))
    request.state.request_id = req_id
    return req_id


class Problema(BaseModel):
    """Esquema de error según RFC 9457 requerido por el contrato."""
    type: str = Field(default="about:blank", description="Identifica el tipo de error.")
    title: str = Field(..., description="Frase corta del error en español.")
    status: int = Field(..., ge=400, le=599, description="Código de estado HTTP.")
    detail: Optional[Union[str, Dict[str, Any], list]] = Field(
        default=None, description="Detalle explicativo del error."
    )
    instance: Optional[str] = Field(default=None, description="URI del recurso que originó el error.")


def crear_respuesta_problema(
    request: Request,
    status: int,
    title: str,
    detail: Optional[Union[str, Dict[str, Any], list]] = None,
    tipo: str = "about:blank",
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """Construye una respuesta JSONResponse con media_type application/problem+json y X-Request-Id."""
    request_id = obtener_request_id(request)
    resp_headers = {
        "X-Request-Id": request_id,
    }
    if headers:
        resp_headers.update(headers)

    problema_dict: Dict[str, Any] = {
        "type": tipo,
        "title": title,
        "status": status,
    }
    if detail is not None:
        problema_dict["detail"] = detail
    problema_dict["instance"] = request.url.path

    return JSONResponse(
        status_code=status,
        content=problema_dict,
        headers=resp_headers,
        media_type=MEDIA_TYPE_PROBLEM,
    )


# ==============================================================================
# Jerarquía de Excepciones de la Aplicación
# ==============================================================================

class AppException(Exception):
    """Excepción base para todos los errores controlados de la aplicación."""
    def __init__(
        self,
        status: int,
        title: str,
        detail: Optional[Union[str, Dict[str, Any], list]] = None,
        tipo: str = "about:blank",
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status = status
        self.title = title
        self.detail = detail
        self.tipo = tipo
        self.headers = headers or {}
        super().__init__(str(detail) if detail else title)


# --- Errores Genéricos (type: about:blank) ---

class SolicitudInvalidaError(AppException):
    """400 - Solicitud inválida (cuerpo, parámetros o encabezados con formato inválido)."""
    def __init__(self, detail: Optional[Union[str, Dict[str, Any], list]] = None):
        super().__init__(status=400, title="Solicitud inválida", detail=detail, tipo="about:blank")


class NoAutenticadoError(AppException):
    """401 - No autenticado (falta el token o no es válido)."""
    def __init__(self, detail: Optional[str] = "Falta el token o no es válido"):
        super().__init__(status=401, title="No autenticado", detail=detail, tipo="about:blank")


class SinPermisoError(AppException):
    """403 - Sin permiso (el token no tiene el permiso necesario o no es dueño del recurso)."""
    def __init__(self, detail: Optional[str] = "El token no tiene el permiso requerido o no es dueño del recurso"):
        super().__init__(status=403, title="Sin permiso", detail=detail, tipo="about:blank")


class NoEncontradoError(AppException):
    """404 - No encontrado (el recurso no existe)."""
    def __init__(self, detail: Optional[str] = "El recurso no existe"):
        super().__init__(status=404, title="No encontrado", detail=detail, tipo="about:blank")


class MetodoNoPermitidoError(AppException):
    """405 - Método no permitido (debe incluir el encabezado Allow)."""
    def __init__(self, allow: str, detail: Optional[str] = "La ruta existe pero no admite el método"):
        super().__init__(
            status=405,
            title="Método no permitido",
            detail=detail,
            tipo="about:blank",
            headers={"Allow": allow},
        )


class CuerpoDemasiadoGrandeError(AppException):
    """413 - Cuerpo demasiado grande (el cuerpo supera 1 MiB)."""
    def __init__(self, detail: Optional[str] = "El cuerpo supera 1 MiB"):
        super().__init__(status=413, title="Cuerpo demasiado grande", detail=detail, tipo="about:blank")


class TipoNoSoportadoError(AppException):
    """415 - Tipo de contenido no soportado (Content-Type no es application/json)."""
    def __init__(self, detail: Optional[str] = "El Content-Type del cuerpo debe ser application/json"):
        super().__init__(status=415, title="Tipo de contenido no soportado", detail=detail, tipo="about:blank")


class ErrorInternoError(AppException):
    """500 - Error interno (error inesperado de M7, sin exponer detalles internos)."""
    def __init__(self, detail: Optional[str] = "Error inesperado de M7"):
        super().__init__(status=500, title="Error interno", detail=detail, tipo="about:blank")


class ServicioNoDisponibleError(AppException):
    """503 - Servicio no disponible (la base de M7 no está disponible)."""
    def __init__(self, detail: Optional[str] = "La base de M7 no está disponible", retry_after: int = 5):
        super().__init__(
            status=503,
            title="Servicio no disponible",
            detail=detail,
            tipo="about:blank",
            headers={"Retry-After": str(retry_after)},
        )


# --- Errores de Dominio (type propio) ---

class ConflictoError(AppException):
    """409 - Conflicto (recurso ya existe, estado incompatible o idempotencia en proceso)."""
    def __init__(
        self,
        detail: Optional[str] = None,
        title: str = "Conflicto",
        tipo: str = "/errores/conflicto",
    ):
        super().__init__(status=409, title=title, detail=detail, tipo=tipo)


class NoProcesableError(AppException):
    """422 - No procesable (regla de negocio no cumplida o Idempotency-Key reusada con otro cuerpo)."""
    def __init__(
        self,
        detail: Optional[str] = None,
        title: str = "No procesable",
        tipo: str = "/errores/no-procesable",
    ):
        super().__init__(status=422, title=title, detail=detail, tipo=tipo)


class DependenciaNoDisponibleError(AppException):
    """503 - Dependencia no disponible (la pasarela de pago externa no respondió a tiempo)."""
    def __init__(
        self,
        detail: Optional[str] = "La pasarela de pago no respondió a tiempo",
        title: str = "Dependencia no disponible",
        tipo: str = "/errores/pasarela-no-disponible",
        retry_after: int = 5,
    ):
        super().__init__(
            status=503,
            title=title,
            detail=detail,
            tipo=tipo,
            headers={"Retry-After": str(retry_after)},
        )


# ==============================================================================
# Manejadores de Excepciones para FastAPI
# ==============================================================================

TITULOS_GENERICOS = {
    400: "Solicitud inválida",
    401: "No autenticado",
    403: "Sin permiso",
    404: "No encontrado",
    405: "Método no permitido",
    413: "Cuerpo demasiado grande",
    415: "Tipo de contenido no soportado",
    500: "Error interno",
    503: "Servicio no disponible",
}


async def app_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Manejador para cualquier excepción derivada de AppException."""
    return crear_respuesta_problema(
        request=request,
        status=getattr(exc, "status", 500),
        title=getattr(exc, "title", "Error"),
        detail=getattr(exc, "detail", None),
        tipo=getattr(exc, "tipo", "about:blank"),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Manejador para errores de validación de esquemas (Pydantic). Mapea a 400 Solicitud inválida."""
    return crear_respuesta_problema(
        request=request,
        status=400,
        title="Solicitud inválida",
        detail="Cuerpo, parámetros o encabezados con formato inválido",
        tipo="about:blank",
    )


async def starlette_http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Manejador para excepciones estándar de Starlette/FastAPI (HTTPException)."""
    status = getattr(exc, "status_code", 500)
    title = TITULOS_GENERICOS.get(status, "Error")
    raw_headers = getattr(exc, "headers", None)
    headers = dict(raw_headers) if raw_headers else {}

    # Si es 503 y no tiene Retry-After, añadirlo
    if status == 503 and "Retry-After" not in headers:
        headers["Retry-After"] = "5"

    return crear_respuesta_problema(
        request=request,
        status=status,
        title=title,
        detail=getattr(exc, "detail", None),
        tipo="about:blank",
        headers=headers,
    )


async def sqlalchemy_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Manejador para errores de conexión o ejecución en la base de datos."""
    return crear_respuesta_problema(
        request=request,
        status=503,
        title="Servicio no disponible",
        detail="La base de datos de M7 no está disponible",
        tipo="about:blank",
        headers={"Retry-After": "5"},
    )


async def general_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Manejador para cualquier error inesperado no controlado."""
    return crear_respuesta_problema(
        request=request,
        status=500,
        title="Error interno",
        detail="Error inesperado de M7",
        tipo="about:blank",
    )


def configurar_manejadores_errores(app: FastAPI) -> None:
    """Registra todos los manejadores de excepciones en la aplicación FastAPI."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

