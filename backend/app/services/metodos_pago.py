"""Medios de pago del cliente (RF-7.2). Solo se guardan marca, últimos 4 dígitos y el token."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import no_encontrado
from app.db import models
from app.schemas.metodos_pago import MetodoPago, MetodoPagoCreate
from app.schemas.pagos import TipoMetodoPago
from app.services.integraciones import DependenciaNoDisponible
from app.services.pasarela import PasarelaNoDisponible, PasarelaPagos, con_timeout


def marca_tarjeta(numero: str) -> str:
    """Marca según el prefijo (IIN) del número de tarjeta."""
    if numero.startswith("4"):
        return "visa"
    if numero[:2] in {"34", "37"}:
        return "amex"
    if 51 <= int(numero[:2]) <= 55 or 2221 <= int(numero[:4]) <= 2720:
        return "mastercard"
    return "otra"


def crear(db: Session, datos: MetodoPagoCreate, pasarela: PasarelaPagos) -> MetodoPago:
    marca = ultimos_4 = token = None
    if datos.tipo != TipoMetodoPago.efectivo:
        dato_sensible = datos.numero_tarjeta or f"{datos.proveedor}:{datos.cliente_id}"
        try:
            token = con_timeout(pasarela.tokenizar, dato_sensible)
        except PasarelaNoDisponible as exc:
            raise DependenciaNoDisponible("La pasarela de pagos") from exc
    if datos.tipo == TipoMetodoPago.tarjeta:
        marca, ultimos_4 = marca_tarjeta(datos.numero_tarjeta), datos.numero_tarjeta[-4:]
    elif datos.tipo == TipoMetodoPago.billetera_virtual:
        marca = datos.proveedor
    metodo = models.MetodoPago(
        id=uuid4(),
        cliente_id=datos.cliente_id,
        tipo=datos.tipo.value,
        marca=marca,
        ultimos_4=ultimos_4,
        alias=datos.alias,
        token_pasarela=token,
        activo=True,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(metodo)
    db.commit()
    return MetodoPago.model_validate(metodo)


def buscar(db: Session, metodo_id: UUID) -> models.MetodoPago:
    metodo = db.get(models.MetodoPago, metodo_id)
    if metodo is None:
        raise no_encontrado("Medio de pago no encontrado")
    return metodo


def listar(db: Session, cliente_id: UUID | None, incluir_bajas: bool = False) -> list[MetodoPago]:
    consulta = select(models.MetodoPago).order_by(models.MetodoPago.creado_en)
    if cliente_id is not None:
        consulta = consulta.where(models.MetodoPago.cliente_id == cliente_id)
    if not incluir_bajas:
        consulta = consulta.where(models.MetodoPago.activo)
    return [MetodoPago.model_validate(m) for m in db.scalars(consulta)]


def dar_de_baja(db: Session, metodo: models.MetodoPago) -> None:
    """Baja lógica: los pagos ya hechos conservan la referencia al medio de pago."""
    if metodo.activo:
        metodo.activo = False
        metodo.eliminado_en = datetime.now(timezone.utc)
        db.commit()
