from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class LiquidacionRequest(BaseModel):
    conductor_id: str
    desde: str
    hasta: str
    cantidad_viajes: int
    bruto: float
    comision: float
    neto: float
    idempotency_key: str


class LiquidacionNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beneficiario_id: UUID
    periodo_desde: date
    periodo_hasta: date


class TransferenciaNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referencia_transferencia: str = Field(min_length=1, max_length=100)
