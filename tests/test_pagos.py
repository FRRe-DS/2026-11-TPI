import uuid


def _crear_pago_autorizado(client, tipo_vehiculo="auto", monto_estimado=2500.0):
    viaje_id = f"viaje-{uuid.uuid4()}"
    cliente_id = str(uuid.uuid4())
    payload = {
        "viaje_id": viaje_id,
        "cliente_id": cliente_id,
        "conductor_id": str(uuid.uuid4()),
        "medio_pago_id": None,
        "tipo_vehiculo": tipo_vehiculo,
        "monto_estimado": monto_estimado,
        "comision_pct": 15.0,
        "idempotency_key": f"auth-{uuid.uuid4()}",
    }
    res = client.post("/pagos/autorizar", json=payload)
    assert res.status_code == 200
    return res.json()["pago"]


def test_autorizar_pago_medio_inexistente(client):
    res = client.post(
        "/pagos/autorizar",
        json={
            "viaje_id": f"viaje-{uuid.uuid4()}",
            "cliente_id": str(uuid.uuid4()),
            "medio_pago_id": "medio-inexistente",
            "tipo_vehiculo": "auto",
            "monto_estimado": 1500.0,
            "idempotency_key": f"auth-{uuid.uuid4()}",
        },
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "M7_MEDIO_PAGO_NO_ENCONTRADO"


def test_capturar_pago_e_idempotencia(client):
    pago = _crear_pago_autorizado(client, monto_estimado=2000.0)
    idem_key = f"cap-{uuid.uuid4()}"

    r1 = client.post(
        "/pagos/capturar",
        json={"pago_id": pago["id"], "monto_final": 2200.0, "idempotency_key": idem_key},
    )
    assert r1.status_code == 200
    assert r1.json()["mensaje"] == "Pago capturado"
    assert r1.json()["pago"]["estado"] == "capturado"
    assert r1.json()["pago"]["monto_final"] == 2200.0

    # Repetición idempotente
    r2 = client.post(
        "/pagos/capturar",
        json={"pago_id": pago["id"], "monto_final": 2200.0, "idempotency_key": idem_key},
    )
    assert r2.status_code == 200
    assert r2.json()["mensaje"] == "Captura ya procesada"


def test_capturar_pago_estado_invalido(client):
    pago = _crear_pago_autorizado(client, monto_estimado=2000.0)
    # Primera captura con key 1
    client.post(
        "/pagos/capturar",
        json={"pago_id": pago["id"], "monto_final": 2000.0, "idempotency_key": f"cap-{uuid.uuid4()}"},
    )
    # Segunda captura con key distinta debe fallar con 409
    res_conflicto = client.post(
        "/pagos/capturar",
        json={"pago_id": pago["id"], "monto_final": 2000.0, "idempotency_key": f"cap-{uuid.uuid4()}"},
    )
    assert res_conflicto.status_code == 409
    assert res_conflicto.json()["detail"] == "M7_PAGO_ESTADO_NO_PERMITE_CAPTURA"


def test_cancelar_pago_con_cargo_e_idempotencia(client):
    pago = _crear_pago_autorizado(client, tipo_vehiculo="moto", monto_estimado=1200.0)
    idem_key = f"canc-{uuid.uuid4()}"

    res = client.post(
        "/pagos/cancelar",
        json={
            "pago_id": pago["id"],
            "motivo": "Cliente canceló luego de asignación",
            "idempotency_key": idem_key,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mensaje"] == "Cargo de cancelación registrado"
    assert data["cargo"] == 250.0  # cargo_cancelacion de moto
    assert data["pago"]["estado"] == "cancelado_con_cargo"

    # Idempotencia
    res_rep = client.post(
        "/pagos/cancelar",
        json={
            "pago_id": pago["id"],
            "motivo": "Cliente canceló luego de asignación",
            "idempotency_key": idem_key,
        },
    )
    assert res_rep.status_code == 200
    assert res_rep.json()["mensaje"] == "Cargo de cancelación ya registrado"


def test_reintegrar_pago_total_y_validacion_monto(client):
    pago = _crear_pago_autorizado(client, monto_estimado=1800.0)
    client.post(
        "/pagos/capturar",
        json={"pago_id": pago["id"], "monto_final": 1800.0, "idempotency_key": f"cap-{uuid.uuid4()}"},
    )

    # Monto mayor al total -> 400
    res_invalido = client.post(
        "/pagos/reintegrar",
        json={
            "pago_id": pago["id"],
            "monto": 2500.0,
            "motivo": "Monto excesivo",
            "idempotency_key": f"reint-{uuid.uuid4()}",
        },
    )
    assert res_invalido.status_code == 400
    assert res_invalido.json()["detail"] == "M7_MONTO_REINTEGRO_INVALIDO"

    # Reintegro total -> estado 'reintegrado'
    idem_reint = f"reint-{uuid.uuid4()}"
    res_total = client.post(
        "/pagos/reintegrar",
        json={
            "pago_id": pago["id"],
            "monto": 1800.0,
            "motivo": "Devolución total",
            "idempotency_key": idem_reint,
        },
    )
    assert res_total.status_code == 200
    assert res_total.json()["pago"]["estado"] == "reintegrado"

    # Idempotencia de reintegro
    res_rep = client.post(
        "/pagos/reintegrar",
        json={
            "pago_id": pago["id"],
            "monto": 1800.0,
            "motivo": "Devolución total",
            "idempotency_key": idem_reint,
        },
    )
    assert res_rep.status_code == 200
    assert res_rep.json()["mensaje"] == "Reintegro ya registrado"


def test_obtener_pago_e_historial_no_encontrado(client):
    res_pago = client.get("/pagos/viaje-inexistente")
    assert res_pago.status_code == 404
    assert res_pago.json()["detail"] == "M7_PAGO_NO_ENCONTRADO"

    res_hist = client.get("/pagos/viaje-inexistente/historial")
    assert res_hist.status_code == 404
    assert res_hist.json()["detail"] == "M7_PAGO_NO_ENCONTRADO"

