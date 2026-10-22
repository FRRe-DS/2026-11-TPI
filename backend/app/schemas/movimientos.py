from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TipoMovimiento(str, Enum):
    autorizacion = "autorizacion"
    autorizacion_sin_respuesta = "autorizacion_sin_respuesta"
    captura = "captura"
    captura_sin_respuesta = "captura_sin_respuesta"
    rechazo = "rechazo"
    anulacion = "anulacion"
    cargo_cancelacion = "cargo_cancelacion"
    reembolso = "reembolso"
    liquidacion_generada = "liquidacion_generada"
    liquidacion_transferida = "liquidacion_transferida"
    liquidacion_anulada = "liquidacion_anulada"


class MovimientoFinanciero(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: TipoMovimiento
    pago_id: UUID | None
    liquidacion_id: UUID | None
    viaje_id: UUID | None
    cliente_id: UUID | None
    beneficiario_id: UUID | None
    monto: Decimal
    moneda: str
    estado_resultante: str | None
    referencia: str | None
    detalle: str | None
    # sub del token que originó el movimiento
    actor: str
    creado_en: datetime
