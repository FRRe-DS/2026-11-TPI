"""Migraciones, inmutabilidad del historial y restricciones de la base."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import models
from app.db.session import engine
from tests.integracion.conftest import autorizar, ejecutar_sql, pago_capturado


def test_las_migraciones_coinciden_con_los_modelos():
    with engine.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), models.Base.metadata)

    assert diferencias == []


def test_el_seed_carga_auto_y_moto():
    tipos = ejecutar_sql("SELECT tipo_vehiculo FROM reglas_tarifa WHERE activa ORDER BY 1").scalars().all()

    assert tipos == ["auto", "moto"]


def test_los_movimientos_no_se_pueden_modificar(client, actores):
    pago_capturado(client, actores)

    with pytest.raises(DBAPIError, match="inmutable"):
        ejecutar_sql("UPDATE movimientos_financieros SET monto = 0")
    with pytest.raises(DBAPIError, match="inmutable"):
        ejecutar_sql("DELETE FROM movimientos_financieros")
    assert ejecutar_sql("SELECT count(*) FROM movimientos_financieros").scalar() == 2


def test_una_sola_regla_activa_por_tipo_en_la_base():
    with pytest.raises(IntegrityError):
        ejecutar_sql(
            "INSERT INTO reglas_tarifa (id, tipo_vehiculo, tarifa_base, precio_por_km, precio_por_minuto,"
            " tarifa_minima, activa) VALUES (gen_random_uuid(), 'auto', 1, 1, 1, 1, true)"
        )


def test_un_solo_cobro_vigente_por_viaje_en_la_base(client, actores):
    pago = autorizar(client, actores).json()

    with pytest.raises(IntegrityError):
        ejecutar_sql(
            "INSERT INTO pagos SELECT gen_random_uuid(), viaje_id, tipo_operacion, reserva_id, estimacion_id,"
            " cliente_id, beneficiario_id, metodo_pago_id, metodo, monto, monto_capturado, monto_reembolsado,"
            " moneda, 'autorizado', referencia_externa, liquidacion_id, creado_en, actualizado_en, capturado_en"
            " FROM pagos WHERE id = :id",
            id=pago["id"],
        )


def test_los_montos_se_guardan_como_numeric():
    tipos = (
        ejecutar_sql(
            "SELECT DISTINCT data_type FROM information_schema.columns"
            " WHERE table_schema = 'public' AND column_name LIKE 'monto%'"
        )
        .scalars()
        .all()
    )

    assert tipos == ["numeric"]
