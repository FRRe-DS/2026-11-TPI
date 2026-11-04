from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import DateTime, Enum, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ParametroTarifa(Base):
    __tablename__ = "parametros_tarifa"

    tipo_vehiculo: Mapped[str] = mapped_column(
        Enum("auto", "moto", name="tipo_vehiculo_enum"),
        primary_key=True,
    )
    base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    por_km: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    por_min: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minima: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cargo_cancelacion: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comision_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tipo_vehiculo": self.tipo_vehiculo,
            "base": float(self.base),
            "por_km": float(self.por_km),
            "por_min": float(self.por_min),
            "minima": float(self.minima),
            "cargo_cancelacion": float(self.cargo_cancelacion),
            "comision_pct": float(self.comision_pct),
            "actualizado_en": self.actualizado_en,
        }

