from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.security import OPERADOR, SERVICIO, Usuario, require_scope
from app.db.session import get_db
from app.schemas.tarifas import (
    Estimacion,
    EstimacionRequest,
    ReglaTarifa,
    ReglaTarifaCreate,
    ReglaTarifaUpdate,
    TarifaFinal,
    TarifaFinalRequest,
    TipoVehiculo,
)
from app.services import tarifas as service
from app.services.integraciones import UbicacionM4, obtener_m4

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])
lectura = require_scope("tarifas:read")


@router.post("/estimaciones", response_model=Estimacion, status_code=status.HTTP_201_CREATED)
def estimar_tarifa(
    datos: EstimacionRequest,
    response: Response,
    usuario: Usuario = Depends(lectura),
    db: Session = Depends(get_db),
    m4: UbicacionM4 | None = Depends(obtener_m4),
):
    """Precio estimado de un viaje (usado por M5 Solicitudes y M9 Reservas). Queda guardado con vencimiento."""
    estimacion = service.estimar(db, datos, usuario, m4)
    response.headers["Location"] = f"/api/v1/tarifas/estimaciones/{estimacion.id}"
    return estimacion


@router.get("/estimaciones/{estimacion_id}", response_model=Estimacion)
def obtener_estimacion(estimacion_id: UUID, _: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    return service.obtener_estimacion(db, estimacion_id)


@router.post("/viajes/{viaje_id}/tarifa-final", response_model=TarifaFinal, status_code=status.HTTP_201_CREATED)
def calcular_tarifa_final(
    viaje_id: UUID,
    datos: TarifaFinalRequest,
    _: Usuario = Depends(require_scope("tarifas:write", SERVICIO, OPERADOR)),
    db: Session = Depends(get_db),
):
    """Calcula y registra el precio final cuando M6 Viajes informa que el viaje terminó."""
    return service.calcular_tarifa_final(db, viaje_id, datos)


@router.get("/viajes/{viaje_id}/tarifa-final", response_model=TarifaFinal)
def obtener_tarifa_final(viaje_id: UUID, _: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    return service.obtener_tarifa_final(db, viaje_id)


@router.get("/reglas", response_model=list[ReglaTarifa])
def listar_reglas(
    tipo_vehiculo: TipoVehiculo | None = None,
    solo_activas: bool = False,
    _: Usuario = Depends(lectura),
    db: Session = Depends(get_db),
):
    return service.listar_reglas(db, tipo_vehiculo, solo_activas)


@router.get("/reglas/{regla_id}", response_model=ReglaTarifa)
def obtener_regla(regla_id: UUID, _: Usuario = Depends(lectura), db: Session = Depends(get_db)):
    return service.obtener_regla(db, regla_id)


@router.post("/reglas", response_model=ReglaTarifa, status_code=status.HTTP_201_CREATED)
def crear_regla(
    datos: ReglaTarifaCreate,
    _: Usuario = Depends(require_scope("tarifas:write", OPERADOR)),
    db: Session = Depends(get_db),
):
    """Crea una regla. Si es activa, desactiva la regla vigente del mismo tipo de vehículo. Solo operador."""
    return service.crear_regla(db, datos)


@router.patch("/reglas/{regla_id}", response_model=ReglaTarifa)
def actualizar_regla(
    regla_id: UUID,
    datos: ReglaTarifaUpdate,
    _: Usuario = Depends(require_scope("tarifas:write", OPERADOR)),
    db: Session = Depends(get_db),
):
    """Modifica una regla. Solo operador."""
    return service.actualizar_regla(db, regla_id, datos)
