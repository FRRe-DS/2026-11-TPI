from typing import Dict, Optional
from fastapi import HTTPException, status


class NoAutenticadoError(HTTPException):
    """Excepción para errores de autenticación (401 Unauthorized)."""

    def __init__(
        self,
        detail: str = "No autenticado",
        headers: Optional[Dict[str, str]] = None,
    ):
        all_headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            all_headers.update(headers)
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=all_headers,
        )


class SinPermisoError(HTTPException):
    """Excepción para errores de autorización o permisos insuficientes (403 Forbidden)."""

    def __init__(
        self,
        detail: str = "Sin permiso",
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=headers,
        )
