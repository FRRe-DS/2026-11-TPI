from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MetodoPago(str, Enum):
    tarjeta = "tarjeta"
    efectivo = "efectivo"
    billetera_virtual = "billetera_virtual"


class EstadoPago(str, Enum):
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"
    reembolsado = "reembolsado"
    reembolsado_parcial = "reembolsado_parcial"


class PagoCreate(BaseModel):
    viaje_id: UUID
    reserva_id: UUID | None = None
    cliente_id: UUID
    # Chofer o dueño del vehículo que recibe el pago en la liquidación
    beneficiario_id: UUID
    monto: Decimal = Field(gt=0)
    metodo: MetodoPago


class Pago(BaseModel):
    id: UUID
    viaje_id: UUID
    reserva_id: UUID | None
    cliente_id: UUID
    beneficiario_id: UUID
    monto: Decimal
    monto_reembolsado: Decimal = Decimal("0")
    moneda: str = "ARS"
    metodo: MetodoPago
    estado: EstadoPago
    referencia_externa: str | None = None
    creado_en: datetime
    actualizado_en: datetime


class ReembolsoCreate(BaseModel):
    # Si se omite, se reembolsa el saldo restante
    monto: Decimal | None = Field(default=None, gt=0)
    motivo: str = Field(min_length=1, max_length=500)


class Reembolso(BaseModel):
    id: UUID
    pago_id: UUID
    monto: Decimal
    motivo: str
    creado_en: datetime


class WebhookPasarela(BaseModel):
    referencia_externa: str
    pago_id: UUID
    estado: EstadoPago
