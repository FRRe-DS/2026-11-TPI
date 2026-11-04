import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Liquidacion(Base):
    __tablename__ = "liquidaciones"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    conductor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    desde: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hasta: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cantidad_viajes: Mapped[int] = mapped_column(Integer, nullable=False)
    bruto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    comision: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    neto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conductor_id": self.conductor_id,
            "desde": self.desde,
            "hasta": self.hasta,
            "cantidad_viajes": self.cantidad_viajes,
            "bruto": float(self.bruto),
            "comision": float(self.comision),
            "neto": float(self.neto),
            "estado": self.estado,
            "idempotency_key": self.idempotency_key,
            "creado_en": self.creado_en,
            "actualizado_en": self.actualizado_en,
        }

