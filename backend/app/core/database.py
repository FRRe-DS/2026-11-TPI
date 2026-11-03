from contextlib import contextmanager
from typing import Generator
import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings


def obtener_conexion() -> pymysql.Connection:
    """Retorna una nueva conexión a MySQL configurada con DictCursor."""
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
    """Context manager para asegurar el cierre de la conexión de forma segura."""
    conexion = obtener_conexion()
    try:
        yield conexion
    finally:
        conexion.close()
