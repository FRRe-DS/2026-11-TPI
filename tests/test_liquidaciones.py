import uuid


def test_crear_y_listar_liquidaciones_con_idempotencia(client):
    conductor_id = str(uuid.uuid4())
    idem_key = f"liq-{uuid.uuid4()}"
    payload = {
        "conductor_id": conductor_id,
        "desde": "2026-11-01 00:00:00",
        "hasta": "2026-11-03 23:59:59",
        "cantidad_viajes": 5,
        "bruto": 15000.0,
        "comision": 2250.0,
        "neto": 12750.0,
        "idempotency_key": idem_key,
    }

    r1 = client.post("/liquidaciones", json=payload)
    assert r1.status_code == 200
    assert r1.json()["mensaje"] == "Liquidación creada"
    liq_id = r1.json()["liquidacion"]["id"]
    assert r1.json()["liquidacion"]["estado"] == "pendiente"

    # Idempotencia
    r2 = client.post("/liquidaciones", json=payload)
    assert r2.status_code == 200
    assert r2.json()["mensaje"] == "Liquidación ya registrada"
    assert r2.json()["liquidacion"]["id"] == liq_id

    # Listado por conductor
    r_list = client.get(f"/liquidaciones/{conductor_id}")
    assert r_list.status_code == 200
    items = r_list.json()
    assert len(items) == 1
    assert items[0]["id"] == liq_id
    assert items[0]["neto"] == 12750.0

