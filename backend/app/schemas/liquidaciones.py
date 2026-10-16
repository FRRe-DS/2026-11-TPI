from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, model_validator


class EstadoLiquidacion(str, Enum):
    pendiente = "pendiente"
    transferida = "transferida"
    anulada = "anulada"


class LiquidacionCreate(BaseModel):
    beneficiario_id: UUID
    periodo_desde: date
    periodo_hasta: date

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.periodo_hasta < self.periodo_desde:
            raise ValueError("periodo_hasta debe ser posterior a periodo_desde")
        return self


class Liquidacion(BaseModel):
    id: UUID
    beneficiario_id: UUID
    periodo_desde: date
    periodo_hasta: date
    pago_ids: list[UUID]
    monto_bruto: Decimal
    comision_plataforma: Decimal
    monto_neto: Decimal
    moneda: str = "ARS"
    estado: EstadoLiquidacion
    referencia_transferencia: str | None = None
    creada_en: datetime
    actualizada_en: datetime


class TransferenciaConfirmacion(BaseModel):
    referencia_transferencia: str


class Saldo(BaseModel):
    beneficiario_id: UUID
    saldo_pendiente_liquidar: Decimal
    liquidado_pendiente_transferir: Decimal
    total_transferido: Decimal
    moneda: str = "ARS"
