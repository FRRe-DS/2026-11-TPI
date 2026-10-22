"""Clientes HTTP de los módulos con los que colabora M7 (M4, M6 y M9).

Los contratos de esos módulos todavía no están publicados: cada interfaz
declara solo lo que M7 necesita y las rutas son supuestos anotados en
docs/decisiones.md. Si la URL de un módulo no está configurada, su
dependencia devuelve None y la operación que lo necesita lo informa.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.errors import ErrorDominio

logger = logging.getLogger("m7.integraciones")


class DependenciaNoDisponible(ErrorDominio):
    def __init__(self, modulo: str):
        super().__init__(
            503,
            "dependencia-no-disponible",
            "Un módulo del que depende la operación no respondió",
            f"{modulo} no respondió a tiempo",
            headers={"Retry-After": "5"},
        )


class RecursoExternoInexistente(ErrorDominio):
    def __init__(self, modulo: str, recurso: str):
        super().__init__(
            422, "recurso-externo-inexistente", "El recurso no existe en el otro módulo", f"{modulo}: {recurso}"
        )


@dataclass(frozen=True)
class RutaEstimada:
    distancia_km: Decimal
    duracion_min: Decimal


@dataclass(frozen=True)
class ViajeExterno:
    id: UUID
    estado: str
    asignado_en: datetime | None = None


@dataclass(frozen=True)
class ReservaExterna:
    id: UUID
    cliente_id: UUID
    estado: str


class UbicacionM4(Protocol):
    def estimar_ruta(
        self, origen: tuple[float, float], destino: tuple[float, float], tipo_vehiculo: str
    ) -> RutaEstimada: ...


class ViajesM6(Protocol):
    def obtener_viaje(self, viaje_id: UUID) -> ViajeExterno: ...


class ReservasM9(Protocol):
    def obtener_reserva(self, reserva_id: UUID) -> ReservaExterna: ...


class ClienteModulo:
    """GET con timeout y reintentos limitados; solo se reintentan errores de red y 5xx."""

    def __init__(self, nombre: str, base_url: str, transport: httpx.BaseTransport | None = None):
        self.nombre = nombre
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=settings.integraciones_timeout_s, transport=transport
        )

    def get(self, ruta: str, params: dict | None = None) -> dict:
        for intento in range(1, settings.integraciones_reintentos + 2):
            try:
                respuesta = self._http.get(ruta, params=params)
            except httpx.TransportError as exc:
                logger.warning("%s sin respuesta (intento %s): %s", self.nombre, intento, exc)
                continue
            if respuesta.status_code >= 500:
                logger.warning("%s respondió %s (intento %s)", self.nombre, respuesta.status_code, intento)
                continue
            if respuesta.status_code == 404:
                raise RecursoExternoInexistente(self.nombre, ruta)
            if respuesta.status_code >= 400:
                logger.error("%s rechazó la consulta %s: %s", self.nombre, ruta, respuesta.status_code)
                raise DependenciaNoDisponible(self.nombre)
            return respuesta.json()
        raise DependenciaNoDisponible(self.nombre)


class ClienteM4(ClienteModulo):
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        super().__init__("M4 Ubicación", base_url, transport)

    def estimar_ruta(self, origen, destino, tipo_vehiculo: str) -> RutaEstimada:
        datos = self.get(
            "/api/v1/rutas/estimacion",
            {
                "origen_lat": origen[0],
                "origen_lng": origen[1],
                "destino_lat": destino[0],
                "destino_lng": destino[1],
                "tipo_vehiculo": tipo_vehiculo,
            },
        )
        return RutaEstimada(Decimal(str(datos["distancia_km"])), Decimal(str(datos["duracion_min"])))


class ClienteM6(ClienteModulo):
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        super().__init__("M6 Viajes", base_url, transport)

    def obtener_viaje(self, viaje_id: UUID) -> ViajeExterno:
        datos = self.get(f"/api/v1/viajes/{viaje_id}")
        asignado_en = datos.get("asignado_en")
        return ViajeExterno(
            id=UUID(datos["id"]),
            estado=datos["estado"],
            asignado_en=datetime.fromisoformat(asignado_en) if asignado_en else None,
        )


class ClienteM9(ClienteModulo):
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        super().__init__("M9 Reservas", base_url, transport)

    def obtener_reserva(self, reserva_id: UUID) -> ReservaExterna:
        datos = self.get(f"/api/v1/reservas/{reserva_id}")
        return ReservaExterna(id=UUID(datos["id"]), cliente_id=UUID(datos["cliente_id"]), estado=datos["estado"])


# Dependencias de FastAPI: los tests las reemplazan por stubs con dependency_overrides


def obtener_m4() -> UbicacionM4 | None:
    return ClienteM4(settings.m4_ubicacion_url) if settings.m4_ubicacion_url else None


def obtener_m6() -> ViajesM6 | None:
    return ClienteM6(settings.m6_viajes_url) if settings.m6_viajes_url else None


def obtener_m9() -> ReservasM9 | None:
    return ClienteM9(settings.m9_reservas_url) if settings.m9_reservas_url else None
