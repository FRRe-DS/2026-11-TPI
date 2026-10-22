"""Reglas de tarifa iniciales para auto y moto

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22
"""

from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Ids fijos para que el seed sea reproducible y reversible
REGLAS = [
    {
        "id": UUID("7a1c0000-0000-4000-8000-000000000001"),
        "tipo_vehiculo": "auto",
        "tarifa_base": Decimal("900"),
        "precio_por_km": Decimal("450"),
        "precio_por_minuto": Decimal("60"),
        "tarifa_minima": Decimal("2000"),
        "activa": True,
    },
    {
        "id": UUID("7a1c0000-0000-4000-8000-000000000002"),
        "tipo_vehiculo": "moto",
        "tarifa_base": Decimal("500"),
        "precio_por_km": Decimal("250"),
        "precio_por_minuto": Decimal("40"),
        "tarifa_minima": Decimal("1200"),
        "activa": True,
    },
]

reglas_tarifa = sa.table(
    "reglas_tarifa",
    sa.column("id", sa.Uuid()),
    sa.column("tipo_vehiculo", sa.String()),
    sa.column("tarifa_base", sa.Numeric(12, 2)),
    sa.column("precio_por_km", sa.Numeric(12, 2)),
    sa.column("precio_por_minuto", sa.Numeric(12, 2)),
    sa.column("tarifa_minima", sa.Numeric(12, 2)),
    sa.column("activa", sa.Boolean()),
)


def upgrade() -> None:
    op.bulk_insert(reglas_tarifa, REGLAS)


def downgrade() -> None:
    op.execute(reglas_tarifa.delete().where(reglas_tarifa.c.id.in_([r["id"] for r in REGLAS])))
