from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.security import require_scope
from app.schemas.tarifas import (
    EstimacionRequest,
    EstimacionResponse,
    ReglaTarifa,
    ReglaTarifaCreate,
    ReglaTarifaUpdate,
    TarifaFinal,
    TarifaFinalRequest,
    TipoVehiculo,
)
from app.services import tarifas as service

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])
lectura = [Depends(require_scope("tarifas:read"))]
escritura = [Depends(require_scope("tarifas:write"))]


@router.post("/estimaciones", response_model=EstimacionResponse, dependencies=lectura)
def estimar_tarifa(datos: EstimacionRequest):
    """Precio estimado de un viaje antes de confirmarlo (usado por M5 Solicitudes y M9 Reservas)."""
    return service.estimar(datos)


@router.post(
    "/viajes/{viaje_id}/tarifa-final",
    response_model=TarifaFinal,
    status_code=status.HTTP_201_CREATED,
    dependencies=escritura,
)
def calcular_tarifa_final(viaje_id: UUID, datos: TarifaFinalRequest):
    """Calcula y registra el precio final cuando M6 Viajes informa que el viaje terminó."""
    return service.calcular_tarifa_final(viaje_id, datos)


@router.get("/viajes/{viaje_id}/tarifa-final", response_model=TarifaFinal, dependencies=lectura)
def obtener_tarifa_final(viaje_id: UUID):
    return service.obtener_tarifa_final(viaje_id)


@router.get("/reglas", response_model=list[ReglaTarifa], dependencies=lectura)
def listar_reglas(tipo_vehiculo: TipoVehiculo | None = None, solo_activas: bool = False):
    return service.listar_reglas(tipo_vehiculo, solo_activas)


@router.get("/reglas/{regla_id}", response_model=ReglaTarifa, dependencies=lectura)
def obtener_regla(regla_id: UUID):
    return service.obtener_regla(regla_id)


@router.post("/reglas", response_model=ReglaTarifa, status_code=status.HTTP_201_CREATED, dependencies=escritura)
def crear_regla(datos: ReglaTarifaCreate):
    """Crea una regla. Si es activa, desactiva la regla vigente del mismo tipo de vehículo."""
    return service.crear_regla(datos)


@router.patch("/reglas/{regla_id}", response_model=ReglaTarifa, dependencies=escritura)
def actualizar_regla(regla_id: UUID, datos: ReglaTarifaUpdate):
    return service.actualizar_regla(regla_id, datos)
