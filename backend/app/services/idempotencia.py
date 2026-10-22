"""Idempotency-Key persistida (RF-7.6).

La clave se guarda con un hash del cuerpo, en la misma transacción que el
recurso que crea. La clave primaria (operacion, clave) hace que dos
solicitudes concurrentes con la misma clave no generen dos efectos.
"""

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import no_procesable
from app.db import models


def hash_cuerpo(datos: dict) -> str:
    """SHA-256 del cuerpo en forma canónica (claves ordenadas, sin espacios)."""
    canonico = json.dumps(datos, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonico.encode()).hexdigest()


def verificar(registro: models.ClaveIdempotencia | None, hash_actual: str) -> UUID | None:
    """Devuelve el recurso ya creado con esa clave, o None si la clave es nueva.

    La misma clave con otro cuerpo es un error del cliente: 422.
    """
    if registro is None:
        return None
    if registro.hash_cuerpo != hash_actual:
        raise no_procesable(
            "idempotency-key-reutilizada",
            "La Idempotency-Key ya se usó con otro cuerpo",
            "Generar una clave nueva para una operación distinta",
        )
    return registro.recurso_id


def buscar(db: Session, operacion: str, clave: str, hash_actual: str) -> UUID | None:
    return verificar(db.get(models.ClaveIdempotencia, (operacion, clave)), hash_actual)


def registrar(db: Session, operacion: str, clave: str, hash_actual: str, recurso_id: UUID) -> None:
    db.add(models.ClaveIdempotencia(operacion=operacion, clave=clave, hash_cuerpo=hash_actual, recurso_id=recurso_id))
