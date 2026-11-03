from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EstimacionRequest(BaseModel):
    tipo_vehiculo: str
    distancia_km: float
    tiempo_min: float


class EstimacionNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_vehiculo: Literal["auto", "moto"]
    distancia_km: float = Field(gt=0)
    duracion_estimada_min: float = Field(gt=0)
    fecha_hora: Optional[datetime] = None
    multiplicador_demanda: float = Field(default=1, ge=1)


class Desglose(BaseModel):
    tarifa_base: float = Field(ge=0)
    cargo_distancia: float = Field(ge=0)
    cargo_tiempo: float = Field(ge=0)
    multiplicador_demanda: float = Field(ge=1)
    total: float = Field(ge=0)


class Estimacion(BaseModel):
    regla_id: str
    moneda: Literal["ARS"] = "ARS"
    desglose: Desglose


class TarifaFinalNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_vehiculo: Literal["auto", "moto"]
    distancia_real_km: float = Field(gt=0)
    duracion_real_min: float = Field(gt=0)
    multiplicador_demanda: float = Field(default=1, ge=1)


class ReglaTarifaNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_vehiculo: Literal["auto", "moto"]
    tarifa_base: float = Field(ge=0)
    precio_por_km: float = Field(ge=0)
    precio_por_minuto: float = Field(ge=0)
    tarifa_minima: float = Field(ge=0)
    cargo_cancelacion: float = Field(default=0, ge=0)
    activa: bool = True


class ReglaTarifaCambios(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tarifa_base: Optional[float] = Field(default=None, ge=0)
    precio_por_km: Optional[float] = Field(default=None, ge=0)
    precio_por_minuto: Optional[float] = Field(default=None, ge=0)
    tarifa_minima: Optional[float] = Field(default=None, ge=0)
    cargo_cancelacion: Optional[float] = Field(default=None, ge=0)
    activa: Optional[bool] = None
