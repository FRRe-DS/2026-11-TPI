"""Errores en application/problem+json (RFC 9457) con el esquema Problema del contrato de M2.

Los errores genéricos usan `type: about:blank` y un título en español; los de
dominio (409, 422 y 503 de una dependencia) tienen su propio `type`.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

logger = logging.getLogger("m7")

MEDIA_TYPE = "application/problem+json"

TITULOS = {
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

# Tipo por defecto de los errores de dominio que no declaran uno propio
TIPOS_POR_DEFECTO = {
    409: ("/errores/conflicto", "El estado del recurso no admite la operación"),
    422: ("/errores/regla-de-negocio", "No se cumple una regla de negocio"),
}


class ErrorDominio(HTTPException):
    """Error de negocio con `type` propio, por ejemplo `/errores/pago-duplicado`."""

    def __init__(
        self,
        status_code: int,
        tipo: str,
        titulo: str,
        detalle: str | None = None,
        headers: dict | None = None,
        **extensiones,
    ):
        super().__init__(status_code, detalle, headers)
        self.tipo = f"/errores/{tipo}"
        self.titulo = titulo
        self.extensiones = extensiones


def no_encontrado(detalle: str) -> HTTPException:
    """404 genérico (type about:blank), como en el contrato de M2."""
    return HTTPException(404, detalle)


def conflicto(tipo: str, titulo: str, detalle: str | None = None, **extensiones) -> ErrorDominio:
    return ErrorDominio(409, tipo, titulo, detalle, **extensiones)


def no_procesable(tipo: str, titulo: str, detalle: str | None = None, **extensiones) -> ErrorDominio:
    return ErrorDominio(422, tipo, titulo, detalle, **extensiones)


def problema(
    request: Request,
    status_code: int,
    detalle: str | None = None,
    tipo: str = "about:blank",
    titulo: str | None = None,
    headers: dict | None = None,
    **extensiones,
) -> JSONResponse:
    cuerpo = {
        "type": tipo,
        "title": titulo or TITULOS.get(status_code, "Error"),
        "status": status_code,
        "instance": request.url.path,
    }
    if detalle:
        cuerpo["detail"] = detalle
    cuerpo.update(extensiones)
    return JSONResponse(cuerpo, status_code=status_code, media_type=MEDIA_TYPE, headers=headers)


def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detalle = exc.detail if isinstance(exc.detail, str) else None
    if isinstance(exc, ErrorDominio):
        return problema(request, exc.status_code, detalle, exc.tipo, exc.titulo, exc.headers, **exc.extensiones)
    if exc.status_code in TIPOS_POR_DEFECTO:
        tipo, titulo = TIPOS_POR_DEFECTO[exc.status_code]
        return problema(request, exc.status_code, detalle, tipo, titulo, exc.headers)
    # Para los genéricos no se repite como detalle la frase estándar de Starlette
    if detalle and detalle == _frase_http(exc.status_code):
        detalle = None
    headers = exc.headers
    if exc.status_code == 405:
        headers = {**(headers or {}), "Allow": _metodos_admitidos(request)}
    return problema(request, exc.status_code, detalle, headers=headers)


def _metodos_admitidos(request: Request) -> str:
    """Starlette solo informa los métodos de la primera ruta; el contrato pide todos los de la ruta."""
    metodos: set[str] = set()
    for ruta in request.app.router.routes:
        coincide, _ = ruta.matches(request.scope)
        if coincide != Match.NONE and getattr(ruta, "methods", None):
            metodos |= ruta.methods
    return ", ".join(sorted(metodos))


def _frase_http(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [
        {"campo": ".".join(str(parte) for parte in error["loc"]), "mensaje": error["msg"]} for error in exc.errors()
    ]
    return problema(request, 400, "Hay datos con formato inválido", errores=errores)


def error_interno(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
    return problema(request, 500)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(Exception, error_interno)
