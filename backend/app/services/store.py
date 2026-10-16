"""Almacenamiento en memoria provisorio hasta conectar Supabase.

Los datos se pierden al reiniciar la API.
"""

from decimal import Decimal
from uuid import UUID, uuid4

from app.schemas.liquidaciones import Liquidacion
from app.schemas.pagos import Pago, Reembolso
from app.schemas.tarifas import ReglaTarifa, TarifaFinal, TipoVehiculo

reglas: dict[UUID, ReglaTarifa] = {}
tarifas_finales: dict[UUID, TarifaFinal] = {}  # clave: viaje_id
pagos: dict[UUID, Pago] = {}
reembolsos: dict[UUID, list[Reembolso]] = {}  # clave: pago_id
idempotencia_pagos: dict[str, UUID] = {}
liquidaciones: dict[UUID, Liquidacion] = {}


def _seed_reglas() -> None:
    valores = {
        TipoVehiculo.moto: ("500", "250", "40", "1200"),
        TipoVehiculo.auto: ("900", "450", "60", "2000"),
        TipoVehiculo.camioneta: ("1200", "550", "75", "2600"),
        TipoVehiculo.van: ("1500", "650", "90", "3200"),
    }
    for tipo, (base, km, minuto, minima) in valores.items():
        regla = ReglaTarifa(
            id=uuid4(),
            tipo_vehiculo=tipo,
            tarifa_base=Decimal(base),
            precio_por_km=Decimal(km),
            precio_por_minuto=Decimal(minuto),
            tarifa_minima=Decimal(minima),
        )
        reglas[regla.id] = regla


_seed_reglas()
