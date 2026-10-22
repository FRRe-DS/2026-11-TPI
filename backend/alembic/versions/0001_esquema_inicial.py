"""Esquema inicial de M7

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MONTO = sa.Numeric(12, 2)


def _fecha(nombre: str, nullable: bool = False) -> sa.Column:
    return sa.Column(nombre, sa.DateTime(timezone=True), nullable=nullable)


def _desglose() -> list[sa.Column]:
    return [
        sa.Column("tarifa_base", MONTO, nullable=False),
        sa.Column("cargo_distancia", MONTO, nullable=False),
        sa.Column("cargo_tiempo", MONTO, nullable=False),
        sa.Column("multiplicador_demanda", sa.Numeric(6, 3), nullable=False),
        sa.Column("total", MONTO, nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "reglas_tarifa",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo_vehiculo", sa.String(20), nullable=False),
        sa.Column("tarifa_base", MONTO, nullable=False),
        sa.Column("precio_por_km", MONTO, nullable=False),
        sa.Column("precio_por_minuto", MONTO, nullable=False),
        sa.Column("tarifa_minima", MONTO, nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_reglas_tarifa_activa", "reglas_tarifa", ["tipo_vehiculo"], unique=True, postgresql_where=sa.text("activa")
    )

    op.create_table(
        "estimaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("regla_id", sa.Uuid(), sa.ForeignKey("reglas_tarifa.id"), nullable=False),
        sa.Column("tipo_vehiculo", sa.String(20), nullable=False),
        sa.Column("distancia_km", sa.Numeric(10, 3), nullable=False),
        sa.Column("duracion_min", sa.Numeric(10, 2), nullable=False),
        *_desglose(),
        sa.Column("creada_por", sa.String(255), nullable=False),
        _fecha("creada_en"),
        _fecha("vence_en"),
    )

    op.create_table(
        "tarifas_finales",
        sa.Column("viaje_id", sa.Uuid(), primary_key=True),
        sa.Column("regla_id", sa.Uuid(), sa.ForeignKey("reglas_tarifa.id"), nullable=False),
        *_desglose(),
        _fecha("calculada_en"),
    )

    op.create_table(
        "metodos_pago",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cliente_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("marca", sa.String(30)),
        sa.Column("ultimos_4", sa.String(4)),
        sa.Column("alias", sa.String(50)),
        sa.Column("token_pasarela", sa.String(100)),
        sa.Column("activo", sa.Boolean(), nullable=False),
        _fecha("creado_en"),
        _fecha("eliminado_en", nullable=True),
    )

    op.create_table(
        "liquidaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("beneficiario_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("periodo_desde", sa.Date(), nullable=False),
        sa.Column("periodo_hasta", sa.Date(), nullable=False),
        sa.Column("monto_bruto", MONTO, nullable=False),
        sa.Column("comision_porcentaje", sa.Numeric(5, 4), nullable=False),
        sa.Column("comision_plataforma", MONTO, nullable=False),
        sa.Column("monto_neto", MONTO, nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("referencia_transferencia", sa.String(100)),
        _fecha("creada_en"),
        _fecha("actualizada_en"),
    )

    op.create_table(
        "pagos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("viaje_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("tipo_operacion", sa.String(30), nullable=False),
        sa.Column("reserva_id", sa.Uuid()),
        sa.Column("estimacion_id", sa.Uuid(), sa.ForeignKey("estimaciones.id")),
        sa.Column("cliente_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("beneficiario_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("metodo_pago_id", sa.Uuid(), sa.ForeignKey("metodos_pago.id")),
        sa.Column("metodo", sa.String(30), nullable=False),
        sa.Column("monto", MONTO, nullable=False),
        sa.Column("monto_capturado", MONTO, nullable=False),
        sa.Column("monto_reembolsado", MONTO, nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("referencia_externa", sa.String(100)),
        sa.Column("liquidacion_id", sa.Uuid(), sa.ForeignKey("liquidaciones.id")),
        _fecha("creado_en"),
        _fecha("actualizado_en"),
        _fecha("capturado_en", nullable=True),
    )
    # Un único cobro vigente por viaje y tipo de operación (RNF-08)
    op.create_index(
        "uq_pagos_viaje_operacion",
        "pagos",
        ["viaje_id", "tipo_operacion"],
        unique=True,
        postgresql_where=sa.text("estado NOT IN ('rechazado', 'anulado')"),
    )

    op.create_table(
        "reembolsos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pago_id", sa.Uuid(), sa.ForeignKey("pagos.id"), nullable=False, index=True),
        sa.Column("monto", MONTO, nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("referencia_externa", sa.String(100)),
        sa.Column("creado_por", sa.String(255), nullable=False),
        _fecha("creado_en"),
    )

    op.create_table(
        "cargos_cancelacion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("viaje_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("cliente_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("estado_viaje", sa.String(30), nullable=False),
        sa.Column("regla_aplicada", sa.String(50), nullable=False),
        sa.Column("monto", MONTO, nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("pago_cargo_id", sa.Uuid(), sa.ForeignKey("pagos.id")),
        sa.Column("pago_anulado_id", sa.Uuid(), sa.ForeignKey("pagos.id")),
        sa.Column("creado_por", sa.String(255), nullable=False),
        _fecha("creado_en"),
    )

    op.create_table(
        "liquidacion_pagos",
        sa.Column("liquidacion_id", sa.Uuid(), sa.ForeignKey("liquidaciones.id"), primary_key=True),
        sa.Column("pago_id", sa.Uuid(), sa.ForeignKey("pagos.id"), primary_key=True),
    )

    op.create_table(
        "claves_idempotencia",
        sa.Column("operacion", sa.String(50), primary_key=True),
        sa.Column("clave", sa.String(255), primary_key=True),
        sa.Column("hash_cuerpo", sa.String(64), nullable=False),
        sa.Column("recurso_id", sa.Uuid(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "movimientos_financieros",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("pago_id", sa.Uuid(), index=True),
        sa.Column("liquidacion_id", sa.Uuid(), index=True),
        sa.Column("viaje_id", sa.Uuid(), index=True),
        sa.Column("cliente_id", sa.Uuid(), index=True),
        sa.Column("beneficiario_id", sa.Uuid(), index=True),
        sa.Column("monto", MONTO, nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("estado_resultante", sa.String(30)),
        sa.Column("referencia", sa.String(100)),
        sa.Column("detalle", sa.String(500)),
        sa.Column("actor", sa.String(255), nullable=False),
        _fecha("creado_en"),
    )
    # Solo INSERT: cualquier UPDATE o DELETE falla (RF-7.7)
    op.execute(
        """
        CREATE FUNCTION impedir_modificacion_movimientos() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'movimientos_financieros es inmutable: solo se permite INSERT';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER movimientos_financieros_inmutables
        BEFORE UPDATE OR DELETE ON movimientos_financieros
        FOR EACH ROW EXECUTE FUNCTION impedir_modificacion_movimientos()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS movimientos_financieros_inmutables ON movimientos_financieros")
    op.execute("DROP FUNCTION IF EXISTS impedir_modificacion_movimientos()")
    for tabla in (
        "movimientos_financieros",
        "claves_idempotencia",
        "liquidacion_pagos",
        "cargos_cancelacion",
        "reembolsos",
        "pagos",
        "liquidaciones",
        "metodos_pago",
        "tarifas_finales",
        "estimaciones",
        "reglas_tarifa",
    ):
        op.drop_table(tabla)
