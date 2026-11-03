from unittest.mock import MagicMock, patch


def test_estimar_tarifa_vehiculo_invalido(client):
    response = client.post(
        "/tarifas/estimar",
        json={
            "tipo_vehiculo": "camion",
            "distancia_km": 10.0,
            "tiempo_min": 15.0,
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["codigo"] == "M7_DATOS_INVALIDOS"
    assert any(err["campo"] == "tipo_vehiculo" for err in detail["errores"])


def test_estimar_tarifa_distancia_negativa(client):
    response = client.post(
        "/tarifas/estimar",
        json={
            "tipo_vehiculo": "auto",
            "distancia_km": -5.0,
            "tiempo_min": 15.0,
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["codigo"] == "M7_DATOS_INVALIDOS"
    assert any(err["campo"] == "distancia_km" for err in detail["errores"])


def test_estimar_tarifa_tiempo_invalido(client):
    response = client.post(
        "/tarifas/estimar",
        json={
            "tipo_vehiculo": "auto",
            "distancia_km": 10.0,
            "tiempo_min": 0.0,
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["codigo"] == "M7_DATOS_INVALIDOS"
    assert any(err["campo"] == "tiempo_min" for err in detail["errores"])


def test_estimar_tarifa_calculo_exitoso(client):
    # Mock de los parámetros de MySQL (auto: base 500, km 150, min 50, minima 800)
    mock_param = {
        "tipo_vehiculo": "auto",
        "base": 500.0,
        "por_km": 150.0,
        "por_min": 50.0,
        "minima": 800.0,
        "cargo_cancelacion": 400.0,
        "comision_pct": 15.0,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_param

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("app.services.tarifas.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = client.post(
            "/tarifas/estimar",
            json={
                "tipo_vehiculo": "auto",
                "distancia_km": 10.0,
                "tiempo_min": 20.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tipo_vehiculo"] == "auto"
        assert data["base"] == 500.0
        assert data["distancia"] == 1500.0
        assert data["tiempo"] == 1000.0
        assert data["total"] == 3000.0
        assert data["moneda"] == "ARS"
