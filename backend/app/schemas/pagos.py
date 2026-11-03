from typing import Literal, Optional
from pydantic import BaseModel


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
