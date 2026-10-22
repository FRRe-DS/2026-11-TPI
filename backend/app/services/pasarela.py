"""Pasarela de pagos detrás de una interfaz, para poder reemplazar la simulada por una real (RF-7.3).

Toda llamada pasa por `con_timeout`: si la pasarela no responde a tiempo se
lanza PasarelaNoDisponible y el pago queda en un estado explícito, nunca
esperando indefinidamente (RNF-13).
"""

import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.core.config import settings

# Tarjetas de prueba (válidas según Luhn) y los tokens que les asigna la pasarela simulada
TARJETA_RECHAZADA = "4000000000000002"
TARJETA_SIN_RESPUESTA = "4000000000000119"
TOKEN_RECHAZADO = "tok_rechazar"  # noqa: S105 - token de prueba, no es un secreto
TOKEN_SIN_RESPUESTA = "tok_sin_respuesta"  # noqa: S105


@dataclass(frozen=True)
class ResultadoPasarela:
    aprobado: bool
    referencia: str
    motivo: str | None = None


class PasarelaNoDisponible(Exception):
    """La pasarela no respondió dentro del timeout o falló la conexión."""


class PasarelaPagos(ABC):
    @abstractmethod
    def tokenizar(self, dato_sensible: str) -> str:
        """Cambia un número de tarjeta o cuenta por un token; M7 solo guarda el token."""

    @abstractmethod
    def autorizar(self, pago_id: UUID, monto: Decimal, token: str | None) -> ResultadoPasarela:
        """Reserva el monto en el medio de pago sin cobrarlo."""

    @abstractmethod
    def capturar(self, referencia: str, monto: Decimal) -> ResultadoPasarela:
        """Cobra un monto previamente autorizado."""

    @abstractmethod
    def anular(self, referencia: str) -> ResultadoPasarela:
        """Libera una autorización que no se va a capturar."""

    @abstractmethod
    def reembolsar(self, referencia: str, monto: Decimal) -> ResultadoPasarela:
        """Devuelve total o parcialmente un monto capturado."""


class PasarelaSimulada(PasarelaPagos):
    """Aprueba todo salvo las tarjetas de prueba TARJETA_RECHAZADA y TARJETA_SIN_RESPUESTA."""

    def __init__(self, demora_sin_respuesta_s: float):
        self.demora_sin_respuesta_s = demora_sin_respuesta_s

    def tokenizar(self, dato_sensible: str) -> str:
        especiales = {TARJETA_RECHAZADA: TOKEN_RECHAZADO, TARJETA_SIN_RESPUESTA: TOKEN_SIN_RESPUESTA}
        return especiales.get(dato_sensible, f"tok_sim_{uuid4().hex}")

    def autorizar(self, pago_id: UUID, monto: Decimal, token: str | None) -> ResultadoPasarela:
        if token == TOKEN_SIN_RESPUESTA:
            time.sleep(self.demora_sin_respuesta_s)
        referencia = f"sim-{uuid4()}"
        if token == TOKEN_RECHAZADO:
            return ResultadoPasarela(False, referencia, "Fondos insuficientes")
        return ResultadoPasarela(True, referencia)

    def capturar(self, referencia: str, monto: Decimal) -> ResultadoPasarela:
        return ResultadoPasarela(True, referencia)

    def anular(self, referencia: str) -> ResultadoPasarela:
        return ResultadoPasarela(True, referencia)

    def reembolsar(self, referencia: str, monto: Decimal) -> ResultadoPasarela:
        return ResultadoPasarela(True, f"{referencia}-r-{uuid4().hex[:8]}")


_ejecutor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="pasarela")


def con_timeout(funcion, *args, timeout_s: float | None = None) -> ResultadoPasarela:
    """Ejecuta una llamada a la pasarela con un tiempo máximo de espera."""
    futuro = _ejecutor.submit(funcion, *args)
    try:
        return futuro.result(timeout=timeout_s if timeout_s is not None else settings.pasarela_timeout_s)
    except FuturesTimeout as exc:
        raise PasarelaNoDisponible("La pasarela no respondió a tiempo") from exc
    except OSError as exc:
        raise PasarelaNoDisponible(f"Error de conexión con la pasarela: {exc}") from exc


_pasarela = PasarelaSimulada(demora_sin_respuesta_s=settings.pasarela_timeout_s + 1)


def obtener_pasarela() -> PasarelaPagos:
    """Dependencia de FastAPI; los tests la reemplazan con dependency_overrides."""
    return _pasarela
