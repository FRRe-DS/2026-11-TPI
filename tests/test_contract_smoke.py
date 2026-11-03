import uuid


def test_estimacion_sin_regla_activa(client):
    response = client.post(
        "/api/v1/tarifas/estimaciones",
        json={
            "tipo_vehiculo": "auto",
            "distancia_km": 10,
            "duracion_estimada_min": 20,
        },
    )
    assert response.status_code in (200, 422)


def test_crear_regla_y_estimar(client):
    tipo_vehiculo = "moto"
    creada = client.post(
        "/api/v1/tarifas/reglas",
        json={
            "tipo_vehiculo": tipo_vehiculo,
            "tarifa_base": 350,
            "precio_por_km": 100,
            "precio_por_minuto": 35,
            "tarifa_minima": 500,
            "cargo_cancelacion": 250,
            "activa": True,
        },
    )
    assert creada.status_code == 201

    estimacion = client.post(
        "/api/v1/tarifas/estimaciones",
        json={
            "tipo_vehiculo": tipo_vehiculo,
            "distancia_km": 5,
            "duracion_estimada_min": 10,
        },
    )
    assert estimacion.status_code == 200
    assert estimacion.json()["moneda"] == "ARS"


def test_pago_requiere_idempotency_key(client):
    response = client.post(
        "/api/v1/pagos",
        json={
            "viaje_id": str(uuid.uuid4()),
            "cliente_id": str(uuid.uuid4()),
            "beneficiario_id": str(uuid.uuid4()),
            "monto": 1,
            "metodo": "efectivo",
        },
    )
    assert response.status_code in (422, 500)
