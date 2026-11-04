import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Pago(Base):
    __tablename__ = "pagos"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    viaje_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    cliente_id: Mapped[str] = mapped_column(String(36), nullable=False)
    conductor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    medio_pago_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("medios_pago.id", name="fk_pagos_medio_pago"),
        nullable=True,
    )
    tipo_vehiculo: Mapped[str] = mapped_column(
        Enum("auto", "moto", name="pago_tipo_vehiculo_enum"),
        nullable=False,
    )
    monto_estimado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_final: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    comision_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "autorizado",
            "rechazado",
            "capturado",
            "cancelado_con_cargo",
            "reintegrado_parcial",
            "reintegrado",
            name="estado_pago_enum",
        ),
        nullable=False,
    )
    capturado_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    liquidacion_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("liquidaciones.id", name="fk_pagos_liquidacion"),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    operaciones: Mapped[List["OperacionFinanciera"]] = relationship(
        back_populates="pago",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "viaje_id": self.viaje_id,
            "cliente_id": self.cliente_id,
            "conductor_id": self.conductor_id,
            "medio_pago_id": self.medio_pago_id,
            "tipo_vehiculo": self.tipo_vehiculo,
            "monto_estimado": float(self.monto_estimado),
            "monto_final": float(self.monto_final) if self.monto_final is not None else None,
            "comision_pct": float(self.comision_pct) if self.comision_pct is not None else None,
            "estado": self.estado,
            "capturado_en": self.capturado_en,
            "liquidacion_id": self.liquidacion_id,
            "creado_en": self.creado_en,
            "actualizado_en": self.actualizado_en,
        }


class OperacionFinanciera(Base):
    __tablename__ = "operaciones_financieras"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    pago_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pagos.id", name="fk_operaciones_pago"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    resultado: Mapped[str] = mapped_column(String(10), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    detalle: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    pago: Mapped["Pago"] = relationship(back_populates="operaciones")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pago_id": self.pago_id,
            "tipo": self.tipo,
            "monto": float(self.monto),
            "resultado": self.resultado,
            "motivo": self.motivo,
            "idempotency_key": self.idempotency_key,
            "detalle": self.detalle,
            "creado_en": self.creado_en,
        }

