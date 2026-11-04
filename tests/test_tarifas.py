def test_obtener_parametros_tarifa(client):
    response = client.get("/tarifas/parametros")
    assert response.status_code == 200
    params = response.json()
    assert len(params) == 2
    por_tipo = {p["tipo_vehiculo"]: p for p in params}
    assert por_tipo["auto"]["base"] == 500.0
    assert por_tipo["moto"]["base"] == 350.0


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
    assert data["minima_aplicada"] is False
    assert data["total"] == 3000.0
    assert data["moneda"] == "ARS"


def test_estimar_tarifa_aplica_minima(client):
    # Subtotal auto con 0.5 km y 1 min = 500 + 75 + 50 = 625 < 800 (mínima)
    response = client.post(
        "/tarifas/estimar",
        json={
            "tipo_vehiculo": "auto",
            "distancia_km": 0.5,
            "tiempo_min": 1.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["minima_aplicada"] is True
    assert data["total"] == 800.0
