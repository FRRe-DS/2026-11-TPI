"""Tablas de M7. Los montos se guardan como NUMERIC, nunca como float."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Numeric, String, Table, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONTO = Numeric(12, 2)

# Estados en los que un cobro ya no ocupa el lugar del viaje (se puede volver a cobrar)
ESTADOS_LIBERADOS = ("rechazado", "anulado")


def _fecha():
    return mapped_column(DateTime(timezone=True))


class Base(DeclarativeBase):
    pass


class ReglaTarifa(Base):
    __tablename__ = "reglas_tarifa"
    # Solo una regla activa por tipo de vehículo, también ante altas concurrentes
    __table_args__ = (Index("uq_reglas_tarifa_activa", "tipo_vehiculo", unique=True, postgresql_where=text("activa")),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tipo_vehiculo: Mapped[str] = mapped_column(String(20))
    tarifa_base: Mapped[Decimal] = mapped_column(MONTO)
    precio_por_km: Mapped[Decimal] = mapped_column(MONTO)
    precio_por_minuto: Mapped[Decimal] = mapped_column(MONTO)
    tarifa_minima: Mapped[Decimal] = mapped_column(MONTO)
    activa: Mapped[bool] = mapped_column(default=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class _Desglose:
    tarifa_base: Mapped[Decimal] = mapped_column(MONTO)
    cargo_distancia: Mapped[Decimal] = mapped_column(MONTO)
    cargo_tiempo: Mapped[Decimal] = mapped_column(MONTO)
    multiplicador_demanda: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    total: Mapped[Decimal] = mapped_column(MONTO)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")


class Estimacion(_Desglose, Base):
    __tablename__ = "estimaciones"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    regla_id: Mapped[UUID] = mapped_column(ForeignKey("reglas_tarifa.id"))
    tipo_vehiculo: Mapped[str] = mapped_column(String(20))
    distancia_km: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    duracion_min: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    creada_por: Mapped[str] = mapped_column(String(255))
    creada_en: Mapped[datetime] = _fecha()
    vence_en: Mapped[datetime] = _fecha()


class TarifaFinal(_Desglose, Base):
    __tablename__ = "tarifas_finales"

    viaje_id: Mapped[UUID] = mapped_column(primary_key=True)
    regla_id: Mapped[UUID] = mapped_column(ForeignKey("reglas_tarifa.id"))
    calculada_en: Mapped[datetime] = _fecha()


class MetodoPago(Base):
    """Medio de pago del cliente. Nunca se guarda el número completo ni el CVV (RF-7.2)."""

    __tablename__ = "metodos_pago"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cliente_id: Mapped[UUID] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    marca: Mapped[str | None] = mapped_column(String(30))
    ultimos_4: Mapped[str | None] = mapped_column(String(4))
    alias: Mapped[str | None] = mapped_column(String(50))
    # Token que entrega la pasarela; reemplaza al número de tarjeta
    token_pasarela: Mapped[str | None] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = _fecha()
    eliminado_en: Mapped[datetime | None] = _fecha()


liquidacion_pagos = Table(
    "liquidacion_pagos",
    Base.metadata,
    Column("liquidacion_id", ForeignKey("liquidaciones.id"), primary_key=True),
    Column("pago_id", ForeignKey("pagos.id"), primary_key=True),
)


class Pago(Base):
    __tablename__ = "pagos"
    # Un único cobro vigente por viaje y tipo de operación (RNF-08). Los
    # rechazados y anulados liberan el lugar para reintentar con otro medio.
    __table_args__ = (
        Index(
            "uq_pagos_viaje_operacion",
            "viaje_id",
            "tipo_operacion",
            unique=True,
            postgresql_where=text("estado NOT IN ('rechazado', 'anulado')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    viaje_id: Mapped[UUID] = mapped_column(index=True)
    tipo_operacion: Mapped[str] = mapped_column(String(30))
    reserva_id: Mapped[UUID | None]
    estimacion_id: Mapped[UUID | None] = mapped_column(ForeignKey("estimaciones.id"))
    cliente_id: Mapped[UUID] = mapped_column(index=True)
    beneficiario_id: Mapped[UUID] = mapped_column(index=True)
    metodo_pago_id: Mapped[UUID | None] = mapped_column(ForeignKey("metodos_pago.id"))
    metodo: Mapped[str] = mapped_column(String(30))
    monto: Mapped[Decimal] = mapped_column(MONTO)
    monto_capturado: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0"))
    monto_reembolsado: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0"))
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    estado: Mapped[str] = mapped_column(String(30))
    referencia_externa: Mapped[str | None] = mapped_column(String(100))
    # Liquidación vigente que incluye el pago; se libera si la liquidación se anula
    liquidacion_id: Mapped[UUID | None] = mapped_column(ForeignKey("liquidaciones.id"))
    creado_en: Mapped[datetime] = _fecha()
    actualizado_en: Mapped[datetime] = _fecha()
    capturado_en: Mapped[datetime | None] = _fecha()


class Reembolso(Base):
    __tablename__ = "reembolsos"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    pago_id: Mapped[UUID] = mapped_column(ForeignKey("pagos.id"), index=True)
    monto: Mapped[Decimal] = mapped_column(MONTO)
    motivo: Mapped[str] = mapped_column(String(500))
    referencia_externa: Mapped[str | None] = mapped_column(String(100))
    creado_por: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = _fecha()


class CargoCancelacion(Base):
    __tablename__ = "cargos_cancelacion"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Una sola cancelación registrada por viaje
    viaje_id: Mapped[UUID] = mapped_column(unique=True)
    cliente_id: Mapped[UUID] = mapped_column(index=True)
    estado_viaje: Mapped[str] = mapped_column(String(30))
    regla_aplicada: Mapped[str] = mapped_column(String(50))
    monto: Mapped[Decimal] = mapped_column(MONTO)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    motivo: Mapped[str] = mapped_column(String(500))
    pago_cargo_id: Mapped[UUID | None] = mapped_column(ForeignKey("pagos.id"))
    pago_anulado_id: Mapped[UUID | None] = mapped_column(ForeignKey("pagos.id"))
    creado_por: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = _fecha()


class ClaveIdempotencia(Base):
    __tablename__ = "claves_idempotencia"

    operacion: Mapped[str] = mapped_column(String(50), primary_key=True)
    clave: Mapped[str] = mapped_column(String(255), primary_key=True)
    # SHA-256 del cuerpo: la misma clave con otro cuerpo se rechaza (RF-7.6)
    hash_cuerpo: Mapped[str] = mapped_column(String(64))
    recurso_id: Mapped[UUID]
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Liquidacion(Base):
    __tablename__ = "liquidaciones"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    beneficiario_id: Mapped[UUID] = mapped_column(index=True)
    periodo_desde: Mapped[date] = mapped_column(Date)
    periodo_hasta: Mapped[date] = mapped_column(Date)
    monto_bruto: Mapped[Decimal] = mapped_column(MONTO)
    comision_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    comision_plataforma: Mapped[Decimal] = mapped_column(MONTO)
    monto_neto: Mapped[Decimal] = mapped_column(MONTO)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    estado: Mapped[str] = mapped_column(String(20))
    referencia_transferencia: Mapped[str | None] = mapped_column(String(100))
    creada_en: Mapped[datetime] = _fecha()
    actualizada_en: Mapped[datetime] = _fecha()

    # Historial de pagos incluidos: se conserva aunque la liquidación se anule
    pagos: Mapped[list[Pago]] = relationship(secondary=liquidacion_pagos, lazy="selectin", order_by=Pago.creado_en)

    @property
    def pago_ids(self) -> list[UUID]:
        return [p.id for p in self.pagos]


class MovimientoFinanciero(Base):
    """Historial financiero inmutable (RF-7.7): un trigger impide UPDATE y DELETE."""

    __tablename__ = "movimientos_financieros"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tipo: Mapped[str] = mapped_column(String(40))
    pago_id: Mapped[UUID | None] = mapped_column(index=True)
    liquidacion_id: Mapped[UUID | None] = mapped_column(index=True)
    viaje_id: Mapped[UUID | None] = mapped_column(index=True)
    cliente_id: Mapped[UUID | None] = mapped_column(index=True)
    beneficiario_id: Mapped[UUID | None] = mapped_column(index=True)
    monto: Mapped[Decimal] = mapped_column(MONTO)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    estado_resultante: Mapped[str | None] = mapped_column(String(30))
    referencia: Mapped[str | None] = mapped_column(String(100))
    detalle: Mapped[str | None] = mapped_column(String(500))
    actor: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = _fecha()
