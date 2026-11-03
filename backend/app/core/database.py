from contextlib import contextmanager
from typing import Generator

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings


def obtener_conexion() -> pymysql.Connection:
    """Retorna una nueva conexion a MySQL configurada con DictCursor."""
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        cursorclass=DictCursor,
    )


@contextmanager
def get_db() -> Generator[pymysql.Connection, None, None]:
    conexion = obtener_conexion()
    try:
        yield conexion
    finally:
        conexion.close()


def asegurar_esquema_contrato() -> None:
    tablas = [
        """
        CREATE TABLE IF NOT EXISTS reglas_tarifa (
          id CHAR(36) PRIMARY KEY,
          tipo_vehiculo ENUM('auto','moto') NOT NULL,
          tarifa_base DECIMAL(12,2) NOT NULL,
          precio_por_km DECIMAL(12,2) NOT NULL,
          precio_por_minuto DECIMAL(12,2) NOT NULL,
          tarifa_minima DECIMAL(12,2) NOT NULL,
          cargo_cancelacion DECIMAL(12,2) NOT NULL DEFAULT 0,
          activa BOOLEAN NOT NULL DEFAULT FALSE,
          creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tarifas_finales (
          viaje_id CHAR(36) PRIMARY KEY, regla_id CHAR(36) NOT NULL, moneda CHAR(3) NOT NULL,
          desglose JSON NOT NULL, calculada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pagos_contrato (
          id CHAR(36) PRIMARY KEY, concepto VARCHAR(30) NOT NULL, viaje_id CHAR(36) NULL,
          reserva_id CHAR(36) NULL, cliente_id CHAR(36) NOT NULL, beneficiario_id CHAR(36) NULL,
          monto DECIMAL(12,2) NOT NULL, monto_reembolsado DECIMAL(12,2) NOT NULL DEFAULT 0,
          moneda CHAR(3) NOT NULL DEFAULT 'ARS', metodo VARCHAR(20) NOT NULL,
          estado VARCHAR(30) NOT NULL, referencia_externa VARCHAR(255) NULL,
          creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS movimientos_contrato (
          id CHAR(36) PRIMARY KEY, pago_id CHAR(36) NOT NULL, tipo VARCHAR(30) NOT NULL,
          monto DECIMAL(12,2) NOT NULL, fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          actor VARCHAR(100) NOT NULL, detalle VARCHAR(500) NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS reembolsos_contrato (
          id CHAR(36) PRIMARY KEY, pago_id CHAR(36) NOT NULL, monto DECIMAL(12,2) NOT NULL,
          motivo VARCHAR(500) NOT NULL, creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS liquidaciones_contrato (
          id CHAR(36) PRIMARY KEY, beneficiario_id CHAR(36) NOT NULL,
          periodo_desde DATE NOT NULL, periodo_hasta DATE NOT NULL, pago_ids JSON NOT NULL,
          monto_bruto DECIMAL(12,2) NOT NULL, comision_plataforma DECIMAL(12,2) NOT NULL,
          cobrado_en_efectivo DECIMAL(12,2) NOT NULL, monto_neto DECIMAL(12,2) NOT NULL,
          moneda CHAR(3) NOT NULL DEFAULT 'ARS', estado VARCHAR(20) NOT NULL,
          referencia_transferencia VARCHAR(100) NULL,
          creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          actualizada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operaciones_idempotentes (
          clave VARCHAR(255) PRIMARY KEY, ruta VARCHAR(255) NOT NULL,
          cuerpo_hash CHAR(64) NOT NULL, estado_http INT NOT NULL,
          respuesta JSON NOT NULL, creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            for tabla in tablas:
                cursor.execute(tabla)
            cursor.execute(
                """
                INSERT INTO reglas_tarifa
                (id,tipo_vehiculo,tarifa_base,precio_por_km,precio_por_minuto,tarifa_minima,cargo_cancelacion,activa)
                SELECT UUID(), tipo_vehiculo, base, por_km, por_min, minima, cargo_cancelacion, TRUE
                FROM parametros_tarifa p
                WHERE NOT EXISTS (
                  SELECT 1 FROM reglas_tarifa r WHERE r.tipo_vehiculo=p.tipo_vehiculo
                )
                """
            )
        conexion.commit()
    finally:
        conexion.close()
