from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.tarifas import (
    DesgloseTarifa,
    EstimacionResponse,
    ReglaTarifa,
    ReglaTarifaCreate,
    ReglaTarifaUpdate,
    TarifaFinal,
    TarifaFinalRequest,
    EstimacionRequest,
    TipoVehiculo,
)
from app.services import store

CENTAVOS = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def listar_reglas(tipo_vehiculo: TipoVehiculo | None, solo_activas: bool) -> list[ReglaTarifa]:
    return [
        r
        for r in store.reglas.values()
        if (tipo_vehiculo is None or r.tipo_vehiculo == tipo_vehiculo) and (not solo_activas or r.activa)
    ]


def obtener_regla(regla_id: UUID) -> ReglaTarifa:
    regla = store.reglas.get(regla_id)
    if regla is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regla de tarifa no encontrada")
    return regla


def crear_regla(datos: ReglaTarifaCreate) -> ReglaTarifa:
    if datos.activa:
        _desactivar_reglas(datos.tipo_vehiculo)
    regla = ReglaTarifa(id=uuid4(), **datos.model_dump())
    store.reglas[regla.id] = regla
    return regla


def actualizar_regla(regla_id: UUID, datos: ReglaTarifaUpdate) -> ReglaTarifa:
    regla = obtener_regla(regla_id)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("activa"):
        _desactivar_reglas(regla.tipo_vehiculo)
    regla = regla.model_copy(update=cambios)
    store.reglas[regla.id] = regla
    return regla


def _desactivar_reglas(tipo_vehiculo: TipoVehiculo) -> None:
    """Solo puede haber una regla activa por tipo de vehículo."""
    for r in listar_reglas(tipo_vehiculo, solo_activas=True):
        store.reglas[r.id] = r.model_copy(update={"activa": False})


def _regla_vigente(tipo_vehiculo: TipoVehiculo) -> ReglaTarifa:
    activas = listar_reglas(tipo_vehiculo, solo_activas=True)
    if not activas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay una regla de tarifa activa para '{tipo_vehiculo.value}'",
        )
    return activas[0]


def _calcular(
    regla: ReglaTarifa, distancia_km: Decimal, duracion_min: Decimal, multiplicador: Decimal
) -> DesgloseTarifa:
    cargo_distancia = regla.precio_por_km * distancia_km
    cargo_tiempo = regla.precio_por_minuto * duracion_min
    subtotal = (regla.tarifa_base + cargo_distancia + cargo_tiempo) * multiplicador
    return DesgloseTarifa(
        tarifa_base=_redondear(regla.tarifa_base),
        cargo_distancia=_redondear(cargo_distancia),
        cargo_tiempo=_redondear(cargo_tiempo),
        multiplicador_demanda=multiplicador,
        total=_redondear(max(subtotal, regla.tarifa_minima)),
    )


def estimar(datos: EstimacionRequest) -> EstimacionResponse:
    regla = _regla_vigente(datos.tipo_vehiculo)
    desglose = _calcular(regla, datos.distancia_km, datos.duracion_estimada_min, datos.multiplicador_demanda)
    return EstimacionResponse(regla_id=regla.id, desglose=desglose)


def calcular_tarifa_final(viaje_id: UUID, datos: TarifaFinalRequest) -> TarifaFinal:
    if viaje_id in store.tarifas_finales:
        raise HTTPException(status.HTTP_409_CONFLICT, "El viaje ya tiene una tarifa final calculada")
    regla = _regla_vigente(datos.tipo_vehiculo)
    desglose = _calcular(regla, datos.distancia_real_km, datos.duracion_real_min, datos.multiplicador_demanda)
    tarifa = TarifaFinal(
        viaje_id=viaje_id,
        regla_id=regla.id,
        desglose=desglose,
        calculada_en=datetime.now(timezone.utc),
    )
    store.tarifas_finales[viaje_id] = tarifa
    return tarifa


def obtener_tarifa_final(viaje_id: UUID) -> TarifaFinal:
    tarifa = store.tarifas_finales.get(viaje_id)
    if tarifa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El viaje no tiene tarifa final calculada")
    return tarifa
