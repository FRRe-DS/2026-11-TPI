from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MONTO_POSITIVO = {"gt": 0, "max_digits": 12, "decimal_places": 2}


class TipoMetodoPago(str, Enum):
    tarjeta = "tarjeta"
    billetera_virtual = "billetera_virtual"
    efectivo = "efectivo"


class TipoOperacion(str, Enum):
    cobro_viaje = "cobro_viaje"
    cargo_cancelacion = "cargo_cancelacion"


class EstadoPago(str, Enum):
    # La pasarela no respondió a la autorización; se resuelve por webhook
    pendiente_confirmacion = "pendiente_confirmacion"
    autorizado = "autorizado"
    rechazado = "rechazado"
    # La pasarela no respondió a la captura; se resuelve por webhook
    captura_pendiente = "captura_pendiente"
    capturado = "capturado"
    anulado = "anulado"
    reembolsado_parcial = "reembolsado_parcial"
    reembolsado = "reembolsado"


class PagoCreate(BaseModel):
    viaje_id: UUID
    reserva_id: UUID | None = None
    # Si se indica y no se envía monto, se autoriza el total de la estimación vigente
    estimacion_id: UUID | None = None
    cliente_id: UUID
    # Chofer o dueño del vehículo que recibe el pago en la liquidación
    beneficiario_id: UUID
    # Medio de pago registrado del cliente (RF-7.2); sin él, el pago es en efectivo
    metodo_pago_id: UUID | None = None
    monto: Decimal | None = Field(default=None, **MONTO_POSITIVO)

    @model_validator(mode="after")
    def validar_monto(self):
        if self.monto is None and self.estimacion_id is None:
            raise ValueError("Indicar monto o estimacion_id")
        return self


class Pago(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    viaje_id: UUID
    tipo_operacion: TipoOperacion
    reserva_id: UUID | None
    estimacion_id: UUID | None
    cliente_id: UUID
    beneficiario_id: UUID
    metodo_pago_id: UUID | None
    metodo: TipoMetodoPago
    monto: Decimal
    monto_capturado: Decimal
    monto_reembolsado: Decimal
    moneda: str = "ARS"
    estado: EstadoPago
    referencia_externa: str | None = None
    liquidacion_id: UUID | None = None
    creado_en: datetime
    actualizado_en: datetime
    capturado_en: datetime | None = None


class CapturaRequest(BaseModel):
    # Si se omite, se usa la tarifa final del viaje o, si no existe, el monto autorizado
    monto: Decimal | None = Field(default=None, **MONTO_POSITIVO)


class ReembolsoCreate(BaseModel):
    # Si se omite, se reembolsa el saldo restante
    monto: Decimal | None = Field(default=None, **MONTO_POSITIVO)
    motivo: str = Field(min_length=1, max_length=500)


class Reembolso(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pago_id: UUID
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None
    creado_en: datetime


class ResultadoPasarela(str, Enum):
    aprobado = "aprobado"
    rechazado = "rechazado"


class WebhookPasarela(BaseModel):
    """Resultado diferido de una autorización o captura que quedó sin respuesta."""

    referencia_externa: str = Field(min_length=1, max_length=100)
    pago_id: UUID
    estado: ResultadoPasarela
