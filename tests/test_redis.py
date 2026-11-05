import json
from unittest.mock import MagicMock, patch
from redis.exceptions import ConnectionError

from app.core import redis as redis_module
from app.core.config import settings
from app.schemas.tarifas import EstimacionRequest
from app.services.tarifas import calcular_estimacion_tarifa, invalidar_cache_tarifas


def test_redis_disabled_returns_none():
    with patch.object(settings, "REDIS_ENABLED", False):
        client = redis_module.get_redis_client()
        assert client is None
        assert redis_module.ping_redis() is False
        assert redis_module.obtener_cache("cualquier_clave") is None
        assert redis_module.guardar_cache("clave", "valor") is False


def test_guardar_y_obtener_cache_mocked():
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    almacen = {}

    def fake_set(key, value, ex=None):
        almacen[key] = value
        return True

    def fake_get(key):
        return almacen.get(key)

    mock_client.set.side_effect = fake_set
    mock_client.get.side_effect = fake_get

    with patch.object(redis_module, "get_redis_client", return_value=mock_client):
        assert redis_module.ping_redis() is True

        datos_prueba = {"base": 500.0, "por_km": 150.0, "por_min": 50.0, "minima": 800.0}
        exito = redis_module.guardar_cache("tarifas:parametro:auto", datos_prueba, ttl_segundos=60)
        assert exito is True

        recuperado = redis_module.obtener_cache("tarifas:parametro:auto")
        assert recuperado == datos_prueba

        # Cache miss
        assert redis_module.obtener_cache("clave_inexistente") is None


def test_redis_fallback_on_connection_error():
    mock_client = MagicMock()
    mock_client.get.side_effect = ConnectionError("Connection refused")
    mock_client.set.side_effect = ConnectionError("Connection refused")

    with patch.object(redis_module, "get_redis_client", return_value=mock_client):
        # Debe capturar el error y devolver None en lectura y False en escritura (degradación elegante)
        assert redis_module.obtener_cache("clave") is None
        assert redis_module.guardar_cache("clave", {"dato": 1}) is False


def test_calcular_estimacion_usa_cache_sin_consultar_db():
    datos_cacheados = {
        "tipo_vehiculo": "auto",
        "base": 500.0,
        "por_km": 150.0,
        "por_min": 50.0,
        "minima": 800.0,
    }

    mock_db = MagicMock()

    with patch("app.services.tarifas.obtener_cache", return_value=datos_cacheados) as mock_get_cache:
        solicitud = EstimacionRequest(tipo_vehiculo="auto", distancia_km=10.0, tiempo_min=20.0)
        resultado = calcular_estimacion_tarifa(solicitud, mock_db)

        # Verificó la clave en Redis
        mock_get_cache.assert_called_once_with("tarifas:parametro:auto")
        # No consultó la base de datos relacional porque estaba en caché
        mock_db.scalar.assert_not_called()

        assert resultado["tipo_vehiculo"] == "auto"
        assert resultado["base"] == 500.0
        assert resultado["distancia"] == 1500.0
        assert resultado["tiempo"] == 1000.0
        assert resultado["total"] == 3000.0


def test_invalidar_cache_tarifas_invoca_patron():
    with patch("app.services.tarifas.eliminar_cache_patron") as mock_eliminar:
        invalidar_cache_tarifas()
        mock_eliminar.assert_called_once_with("tarifas:*")

