from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.pagos import TipoMetodoPago


def luhn_valido(numero: str) -> bool:
    """Dígito verificador de las tarjetas (algoritmo de Luhn)."""
    total = 0
    for posicion, digito in enumerate(int(d) for d in reversed(numero)):
        if posicion % 2 == 1:
            digito *= 2
            if digito > 9:
                digito -= 9
        total += digito
    return total % 10 == 0


class MetodoPagoCreate(BaseModel):
    """El número de tarjeta solo se usa para tokenizar: no se guarda ni se devuelve.

    No existe un campo para el CVV; cualquier campo desconocido se rechaza.
    """

    model_config = ConfigDict(extra="forbid")

    cliente_id: UUID
    tipo: TipoMetodoPago
    numero_tarjeta: str | None = Field(default=None, pattern=r"^\d{13,19}$")
    # Proveedor de la billetera virtual, por ejemplo "mercadopago"
    proveedor: str | None = Field(default=None, min_length=1, max_length=30)
    alias: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def validar_datos_del_tipo(self):
        if self.tipo == TipoMetodoPago.tarjeta:
            if not self.numero_tarjeta:
                raise ValueError("Una tarjeta requiere numero_tarjeta")
            if not luhn_valido(self.numero_tarjeta):
                raise ValueError("El número de tarjeta no es válido")
            if self.proveedor:
                raise ValueError("proveedor solo aplica a billetera_virtual")
        elif self.tipo == TipoMetodoPago.billetera_virtual:
            if not self.proveedor:
                raise ValueError("Una billetera virtual requiere proveedor")
            if self.numero_tarjeta:
                raise ValueError("numero_tarjeta solo aplica a tarjeta")
        elif self.numero_tarjeta or self.proveedor:
            raise ValueError("El efectivo no lleva numero_tarjeta ni proveedor")
        return self


class MetodoPago(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cliente_id: UUID
    tipo: TipoMetodoPago
    marca: str | None
    ultimos_4: str | None
    alias: str | None
    activo: bool
    creado_en: datetime
    eliminado_en: datetime | None = None
