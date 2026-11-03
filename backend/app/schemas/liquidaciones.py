from pydantic import BaseModel


class LiquidacionRequest(BaseModel):
    conductor_id: str
    desde: str
    hasta: str
    cantidad_viajes: int
    bruto: float
    comision: float
    neto: float
    idempotency_key: str
