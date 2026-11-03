from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

UUID4 = UUID


class PagoAutorizarRequest(BaseModel):
    viaje_id: str
    cliente_id: str
    conductor_id: Optional[str] = None
    medio_pago_id: Optional[str] = None
    tipo_vehiculo: Literal["auto", "moto"]
    monto_estimado: float
    comision_pct: Optional[float] = None
    idempotency_key: str


class PagoCapturarRequest(BaseModel):
    pago_id: str
    monto_final: Optional[float] = None
    idempotency_key: str


class CargoCancelacionRequest(BaseModel):
    pago_id: str
    motivo: str = "Cancelación solicitada por el cliente"
    idempotency_key: str


class ReintegroRequest(BaseModel):
    pago_id: str
    monto: float
    motivo: str = "Reintegro por ajuste posterior"
    idempotency_key: str


class PagoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    viaje_id: UUID4
    reserva_id: Optional[UUID4] = None
    cliente_id: UUID4
    beneficiario_id: UUID4
    monto: float = Field(gt=0, le=1_000_000_000)
    metodo: Literal["tarjeta", "efectivo", "billetera_virtual"]


class CargoCancelacionNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    viaje_id: Optional[UUID4] = None
    reserva_id: Optional[UUID4] = None
    cliente_id: UUID4
    tipo_vehiculo: Literal["auto", "moto"]
    metodo: Literal["tarjeta", "billetera_virtual"]
    motivo: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validar_origen(self):
        if self.viaje_id is None and self.reserva_id is None:
            raise ValueError("Se requiere viaje_id o reserva_id")
        return self


class AvisoPasarela(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referencia_externa: str = Field(min_length=1)
    pago_id: UUID4
    estado: Literal["aprobado", "rechazado"]


class ReembolsoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    motivo: str = Field(min_length=1, max_length=500)
