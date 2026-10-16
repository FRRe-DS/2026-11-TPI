from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TipoVehiculo(str, Enum):
    auto = "auto"
    moto = "moto"
    camioneta = "camioneta"
    van = "van"


class ReglaTarifaBase(BaseModel):
    tipo_vehiculo: TipoVehiculo
    tarifa_base: Decimal = Field(ge=0)
    precio_por_km: Decimal = Field(ge=0)
    precio_por_minuto: Decimal = Field(ge=0)
    tarifa_minima: Decimal = Field(ge=0)
    activa: bool = True


class ReglaTarifaCreate(ReglaTarifaBase):
    pass


class ReglaTarifaUpdate(BaseModel):
    tarifa_base: Decimal | None = Field(default=None, ge=0)
    precio_por_km: Decimal | None = Field(default=None, ge=0)
    precio_por_minuto: Decimal | None = Field(default=None, ge=0)
    tarifa_minima: Decimal | None = Field(default=None, ge=0)
    activa: bool | None = None


class ReglaTarifa(ReglaTarifaBase):
    id: UUID


class EstimacionRequest(BaseModel):
    tipo_vehiculo: TipoVehiculo
    distancia_km: Decimal = Field(gt=0)
    duracion_estimada_min: Decimal = Field(gt=0)
    fecha_hora: datetime | None = None
    multiplicador_demanda: Decimal = Field(default=Decimal("1"), ge=1)


class TarifaFinalRequest(BaseModel):
    tipo_vehiculo: TipoVehiculo
    distancia_real_km: Decimal = Field(gt=0)
    duracion_real_min: Decimal = Field(gt=0)
    multiplicador_demanda: Decimal = Field(default=Decimal("1"), ge=1)


class DesgloseTarifa(BaseModel):
    tarifa_base: Decimal
    cargo_distancia: Decimal
    cargo_tiempo: Decimal
    multiplicador_demanda: Decimal
    total: Decimal


class EstimacionResponse(BaseModel):
    regla_id: UUID
    moneda: str = "ARS"
    desglose: DesgloseTarifa


class TarifaFinal(EstimacionResponse):
    viaje_id: UUID
    calculada_en: datetime
