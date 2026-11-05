import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MedioPago(Base):
    __tablename__ = "medios_pago"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    cliente_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    alias: Mapped[str] = mapped_column(String(40), nullable=False)
    ultimos4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    predeterminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "tipo": self.tipo,
            "alias": self.alias,
            "ultimos4": self.ultimos4,
            "predeterminado": bool(self.predeterminado),
            "creado_en": self.creado_en,
        }

