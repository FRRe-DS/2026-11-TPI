from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EstadoViaje(str, Enum):
    """Estados del viaje que importan para el cargo; supuesto hasta que M6 publique su contrato."""

    solicitado = "solicitado"
    asignado = "asignado"
    conductor_en_punto = "conductor_en_punto"
    en_curso = "en_curso"
    finalizado = "finalizado"
    cancelado = "cancelado"


class ReglaCargo(str, Enum):
    sin_asignar = "sin_asignar"
    dentro_periodo_gracia = "dentro_periodo_gracia"
    asignado_fuera_de_gracia = "asignado_fuera_de_gracia"
    conductor_en_punto = "conductor_en_punto"


class CancelacionCreate(BaseModel):
    viaje_id: UUID
    cliente_id: UUID
    motivo: str = Field(min_length=1, max_length=500)
    # Si no se envían, se consultan a M6
    estado_viaje: EstadoViaje | None = None
    asignado_en: datetime | None = None
    # Momento de la cancelación; por defecto, ahora
    cancelado_en: datetime | None = None


class CargoCancelacion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    viaje_id: UUID
    cliente_id: UUID
    estado_viaje: EstadoViaje
    regla_aplicada: ReglaCargo
    monto: Decimal
    moneda: str = "ARS"
    motivo: str
    # Pago con el que se cobró el cargo (si había un medio de pago autorizado)
    pago_cargo_id: UUID | None = None
    # Autorización del viaje que se liberó al cancelar
    pago_anulado_id: UUID | None = None
    creado_en: datetime
