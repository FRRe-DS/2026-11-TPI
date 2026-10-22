from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflicto, no_encontrado, no_procesable
from app.core.security import Usuario
from app.db import models
from app.schemas.tarifas import (
    DesgloseTarifa,
    Estimacion,
    EstimacionRequest,
    ReglaTarifa,
    ReglaTarifaCreate,
    ReglaTarifaUpdate,
    TarifaFinal,
    TarifaFinalRequest,
    TipoVehiculo,
)
from app.services.integraciones import UbicacionM4

CENTAVOS = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calcular_desglose(
    regla: ReglaTarifa, distancia_km: Decimal, duracion_min: Decimal, multiplicador: Decimal
) -> DesgloseTarifa:
    """Cálculo puro de la tarifa: (base + distancia + tiempo) * multiplicador, con tarifa mínima."""
    cargo_distancia = regla.precio_por_km * distancia_km
    cargo_tiempo = regla.precio_por_minuto * duracion_min
    subtotal = (regla.tarifa_base + cargo_distancia + cargo_tiempo) * multiplicador
    return DesgloseTarifa(
        tarifa_base=redondear(regla.tarifa_base),
        cargo_distancia=redondear(cargo_distancia),
        cargo_tiempo=redondear(cargo_tiempo),
        multiplicador_demanda=multiplicador,
        total=redondear(max(subtotal, regla.tarifa_minima)),
    )


def listar_reglas(db: Session, tipo_vehiculo: TipoVehiculo | None, solo_activas: bool) -> list[ReglaTarifa]:
    consulta = select(models.ReglaTarifa).order_by(models.ReglaTarifa.creada_en)
    if tipo_vehiculo is not None:
        consulta = consulta.where(models.ReglaTarifa.tipo_vehiculo == tipo_vehiculo.value)
    if solo_activas:
        consulta = consulta.where(models.ReglaTarifa.activa)
    return [ReglaTarifa.model_validate(r) for r in db.scalars(consulta)]


def _buscar_regla(db: Session, regla_id: UUID) -> models.ReglaTarifa:
    regla = db.get(models.ReglaTarifa, regla_id)
    if regla is None:
        raise no_encontrado("Regla de tarifa no encontrada")
    return regla


def obtener_regla(db: Session, regla_id: UUID) -> ReglaTarifa:
    return ReglaTarifa.model_validate(_buscar_regla(db, regla_id))


def _desactivar_reglas(db: Session, tipo_vehiculo: str) -> None:
    """Solo puede haber una regla activa por tipo de vehículo."""
    db.execute(
        update(models.ReglaTarifa)
        .where(models.ReglaTarifa.tipo_vehiculo == tipo_vehiculo, models.ReglaTarifa.activa)
        .values(activa=False)
    )


def _guardar(db: Session, regla: models.ReglaTarifa) -> ReglaTarifa:
    try:
        db.commit()
    except IntegrityError as exc:
        # Otra regla del mismo tipo se activó en paralelo (índice único parcial)
        db.rollback()
        raise conflicto("regla-activa-duplicada", "Ya hay otra regla activa para ese tipo de vehículo") from exc
    return ReglaTarifa.model_validate(regla)


def crear_regla(db: Session, datos: ReglaTarifaCreate) -> ReglaTarifa:
    if datos.activa:
        _desactivar_reglas(db, datos.tipo_vehiculo.value)
    regla = models.ReglaTarifa(**datos.model_dump(exclude={"tipo_vehiculo"}), tipo_vehiculo=datos.tipo_vehiculo.value)
    db.add(regla)
    return _guardar(db, regla)


def actualizar_regla(db: Session, regla_id: UUID, datos: ReglaTarifaUpdate) -> ReglaTarifa:
    regla = _buscar_regla(db, regla_id)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("activa") and not regla.activa:
        _desactivar_reglas(db, regla.tipo_vehiculo)
    for campo, valor in cambios.items():
        setattr(regla, campo, valor)
    return _guardar(db, regla)


def _regla_vigente(db: Session, tipo_vehiculo: TipoVehiculo) -> ReglaTarifa:
    activas = listar_reglas(db, tipo_vehiculo, solo_activas=True)
    if not activas:
        raise no_procesable(
            "sin-regla-activa",
            "No hay una regla de tarifa activa",
            f"No hay una regla de tarifa activa para '{tipo_vehiculo.value}'",
        )
    return activas[0]


def _desglose(fila: models.Estimacion | models.TarifaFinal) -> DesgloseTarifa:
    return DesgloseTarifa(
        tarifa_base=fila.tarifa_base,
        cargo_distancia=fila.cargo_distancia,
        cargo_tiempo=fila.cargo_tiempo,
        multiplicador_demanda=fila.multiplicador_demanda,
        total=fila.total,
    )


def _estimacion(fila: models.Estimacion) -> Estimacion:
    return Estimacion(
        id=fila.id,
        regla_id=fila.regla_id,
        tipo_vehiculo=fila.tipo_vehiculo,
        distancia_km=fila.distancia_km,
        duracion_estimada_min=fila.duracion_min,
        moneda=fila.moneda,
        desglose=_desglose(fila),
        creada_en=fila.creada_en,
        vence_en=fila.vence_en,
        vigente=fila.vence_en > datetime.now(timezone.utc),
    )


def _medidas_de_ruta(datos: EstimacionRequest, m4: UbicacionM4 | None) -> tuple[Decimal, Decimal]:
    """Usa distancia y duración si llegan; si no, se las pide a M4 con origen y destino."""
    if datos.distancia_km is not None and datos.duracion_estimada_min is not None:
        return datos.distancia_km, datos.duracion_estimada_min
    if m4 is None:
        raise no_procesable(
            "ruta-no-disponible",
            "No se puede calcular la ruta",
            "M4 no está configurado: enviar distancia_km y duracion_estimada_min",
        )
    ruta = m4.estimar_ruta(
        (datos.origen.lat, datos.origen.lng), (datos.destino.lat, datos.destino.lng), datos.tipo_vehiculo.value
    )
    return ruta.distancia_km, ruta.duracion_min


def estimar(db: Session, datos: EstimacionRequest, usuario: Usuario, m4: UbicacionM4 | None = None) -> Estimacion:
    """Calcula y guarda la estimación para que M5 o M9 la referencien por id (RF-7.1)."""
    regla = _regla_vigente(db, datos.tipo_vehiculo)
    distancia, duracion = _medidas_de_ruta(datos, m4)
    desglose = calcular_desglose(regla, distancia, duracion, datos.multiplicador_demanda)
    ahora = datetime.now(timezone.utc)
    fila = models.Estimacion(
        id=uuid4(),
        regla_id=regla.id,
        tipo_vehiculo=datos.tipo_vehiculo.value,
        distancia_km=distancia,
        duracion_min=duracion,
        moneda="ARS",
        creada_por=usuario.sub,
        creada_en=ahora,
        vence_en=ahora + timedelta(minutes=settings.estimacion_vigencia_min),
        **desglose.model_dump(),
    )
    db.add(fila)
    db.commit()
    return _estimacion(fila)


def obtener_estimacion(db: Session, estimacion_id: UUID) -> Estimacion:
    fila = db.get(models.Estimacion, estimacion_id)
    if fila is None:
        raise no_encontrado("Estimación no encontrada")
    return _estimacion(fila)


def _tarifa_final(fila: models.TarifaFinal) -> TarifaFinal:
    return TarifaFinal(
        viaje_id=fila.viaje_id,
        regla_id=fila.regla_id,
        moneda=fila.moneda,
        calculada_en=fila.calculada_en,
        desglose=_desglose(fila),
    )


def calcular_tarifa_final(db: Session, viaje_id: UUID, datos: TarifaFinalRequest) -> TarifaFinal:
    if db.get(models.TarifaFinal, viaje_id) is not None:
        raise conflicto("tarifa-final-existente", "El viaje ya tiene una tarifa final calculada")
    regla = _regla_vigente(db, datos.tipo_vehiculo)
    desglose = calcular_desglose(regla, datos.distancia_real_km, datos.duracion_real_min, datos.multiplicador_demanda)
    fila = models.TarifaFinal(
        viaje_id=viaje_id,
        regla_id=regla.id,
        moneda="ARS",
        calculada_en=datetime.now(timezone.utc),
        **desglose.model_dump(),
    )
    db.add(fila)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflicto("tarifa-final-existente", "El viaje ya tiene una tarifa final calculada") from exc
    return _tarifa_final(fila)


def obtener_tarifa_final(db: Session, viaje_id: UUID) -> TarifaFinal:
    fila = db.get(models.TarifaFinal, viaje_id)
    if fila is None:
        raise no_encontrado("El viaje no tiene tarifa final calculada")
    return _tarifa_final(fila)
