from pydantic import BaseModel


class EstimacionRequest(BaseModel):
    tipo_vehiculo: str
    distancia_km: float
    tiempo_min: float
