from typing import Optional
from pydantic import BaseModel


class MedioPagoRequest(BaseModel):
    cliente_id: str
    tipo: str
    alias: str
    ultimos4: Optional[str] = None
    predeterminado: bool = False
