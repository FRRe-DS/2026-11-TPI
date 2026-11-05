import json
import logging
from typing import Any, Optional

import redis
from app.core.config import settings

logger = logging.getLogger("m7.redis")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Retorna una instancia singleton del cliente de Redis.
    
    Si Redis está deshabilitado o no responde, retorna None sin lanzar excepción.
    """
    global _redis_client

    if not settings.REDIS_ENABLED:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        except Exception as exc:
            logger.warning(f"No se pudo inicializar el cliente de Redis: {exc}")
            _redis_client = None

    return _redis_client


def ping_redis() -> bool:
    """Verifica si el servidor de Redis está activo y responde."""
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.ping())
    except Exception as exc:
        logger.debug(f"Fallo al conectar con Redis (ping): {exc}")
        return False


def obtener_cache(clave: str) -> Optional[Any]:
    """Obtiene un valor serializado en JSON desde Redis.
    
    Retorna None en caso de cache miss, Redis deshabilitado o falla de conexión (fallback tolerante).
    """
    client = get_redis_client()
    if not client:
        return None

    try:
        dato = client.get(clave)
        if dato is not None:
            return json.loads(dato)
    except Exception as exc:
        logger.warning(f"Error al leer de Redis [clave={clave}]: {exc}. Continuando con la base de datos.")
    return None


def guardar_cache(clave: str, valor: Any, ttl_segundos: Optional[int] = None) -> bool:
    """Guarda un valor serializado en JSON en Redis con un tiempo de expiración (TTL)."""
    client = get_redis_client()
    if not client:
        return False

    ttl = ttl_segundos if ttl_segundos is not None else settings.REDIS_CACHE_TTL_SEGUNDOS
    try:
        payload = json.dumps(valor, default=str)
        client.set(clave, payload, ex=ttl)
        return True
    except Exception as exc:
        logger.warning(f"Error al escribir en Redis [clave={clave}]: {exc}")
        return False


def eliminar_cache(clave: str) -> bool:
    """Elimina una clave específica de la caché."""
    client = get_redis_client()
    if not client:
        return False
    try:
        client.delete(clave)
        return True
    except Exception as exc:
        logger.warning(f"Error al eliminar de Redis [clave={clave}]: {exc}")
        return False


def eliminar_cache_patron(patron: str) -> int:
    """Elimina todas las claves que coincidan con un patrón (ej: 'tarifas:*')."""
    client = get_redis_client()
    if not client:
        return 0
    try:
        claves = list(client.scan_iter(match=patron))
        if claves:
            return client.delete(*claves)
        return 0
    except Exception as exc:
        logger.warning(f"Error al invalidar patrón en Redis [patron={patron}]: {exc}")
        return 0

