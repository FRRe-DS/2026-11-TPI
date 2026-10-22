from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MONTO = {"ge": 0, "max_digits": 12, "decimal_places": 2}


class TipoVehiculo(str, Enum):
    auto = "auto"
    moto = "moto"


class ReglaTarifaBase(BaseModel):
    tipo_vehiculo: TipoVehiculo
    tarifa_base: Decimal = Field(**MONTO)
    precio_por_km: Decimal = Field(**MONTO)
    precio_por_minuto: Decimal = Field(**MONTO)
    tarifa_minima: Decimal = Field(**MONTO)
    activa: bool = True


class ReglaTarifaCreate(ReglaTarifaBase):
    pass


class ReglaTarifaUpdate(BaseModel):
    tarifa_base: Decimal | None = Field(default=None, **MONTO)
    precio_por_km: Decimal | None = Field(default=None, **MONTO)
    precio_por_minuto: Decimal | None = Field(default=None, **MONTO)
    tarifa_minima: Decimal | None = Field(default=None, **MONTO)
    activa: bool | None = None


class ReglaTarifa(ReglaTarifaBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class Coordenada(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class EstimacionRequest(BaseModel):
    """Con distancia y duración se calcula directo; con origen y destino se consultan a M4."""

    tipo_vehiculo: TipoVehiculo
    distancia_km: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    duracion_estimada_min: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    origen: Coordenada | None = None
    destino: Coordenada | None = None
    fecha_hora: datetime | None = None
    multiplicador_demanda: Decimal = Field(default=Decimal("1"), ge=1, le=10, max_digits=6, decimal_places=3)

    @model_validator(mode="after")
    def validar_ruta(self):
        tiene_medidas = self.distancia_km is not None and self.duracion_estimada_min is not None
        tiene_puntos = self.origen is not None and self.destino is not None
        if not (tiene_medidas or tiene_puntos):
            raise ValueError("Indicar distancia_km y duracion_estimada_min, u origen y destino")
        return self


class TarifaFinalRequest(BaseModel):
    tipo_vehiculo: TipoVehiculo
    distancia_real_km: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    duracion_real_min: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    multiplicador_demanda: Decimal = Field(default=Decimal("1"), ge=1, le=10, max_digits=6, decimal_places=3)


class DesgloseTarifa(BaseModel):
    tarifa_base: Decimal
    cargo_distancia: Decimal
    cargo_tiempo: Decimal
    multiplicador_demanda: Decimal
    total: Decimal


class Estimacion(BaseModel):
    id: UUID
    regla_id: UUID
    tipo_vehiculo: TipoVehiculo
    distancia_km: Decimal
    duracion_estimada_min: Decimal
    moneda: str = "ARS"
    desglose: DesgloseTarifa
    creada_en: datetime
    vence_en: datetime
    vigente: bool


class TarifaFinal(BaseModel):
    viaje_id: UUID
    regla_id: UUID
    moneda: str = "ARS"
    desglose: DesgloseTarifa
    calculada_en: datetime
