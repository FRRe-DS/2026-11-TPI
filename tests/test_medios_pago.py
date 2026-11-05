import uuid


def test_registrar_medio_pago_tipo_invalido(client):
    response = client.post(
        "/pagos/medios",
        json={
            "cliente_id": "cliente-123",
            "tipo": "cheque",
            "alias": "Mi cheque",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["codigo"] == "M7_DATOS_INVALIDOS"
    assert any(err["campo"] == "tipo" for err in detail["errores"])


def test_registrar_medio_pago_alias_vacio(client):
    response = client.post(
        "/pagos/medios",
        json={
            "cliente_id": "cliente-123",
            "tipo": "tarjeta",
            "alias": "   ",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any(err["campo"] == "alias" for err in detail["errores"])


def test_registrar_medio_pago_alias_demasiado_largo(client):
    response = client.post(
        "/pagos/medios",
        json={
            "cliente_id": "cliente-123",
            "tipo": "billetera",
            "alias": "A" * 41,
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any(err["error"] == "ALIAS DEMASIADO LARGO" for err in detail["errores"])


def test_registrar_medio_pago_ultimos4_invalido(client):
    response = client.post(
        "/pagos/medios",
        json={
            "cliente_id": "cliente-123",
            "tipo": "tarjeta",
            "alias": "Visa Débito",
            "ultimos4": "12A4",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any(err["campo"] == "ultimos4" for err in detail["errores"])


def test_registrar_y_actualizar_medio_predeterminado(client):
    cliente_id = str(uuid.uuid4())

    r1 = client.post(
        "/pagos/medios",
        json={
            "cliente_id": cliente_id,
            "tipo": "tarjeta",
            "alias": "Visa",
            "ultimos4": "1111",
            "predeterminado": True,
        },
    )
    assert r1.status_code == 200
    id_primero = r1.json()["id"]

    r2 = client.post(
        "/pagos/medios",
        json={
            "cliente_id": cliente_id,
            "tipo": "billetera",
            "alias": "MercadoPago",
            "predeterminado": True,
        },
    )
    assert r2.status_code == 200
    id_segundo = r2.json()["id"]

    lista = client.get(f"/pagos/medios/{cliente_id}").json()
    assert len(lista) == 2
    por_id = {m["id"]: m for m in lista}
    assert por_id[id_segundo]["predeterminado"] is True
    assert por_id[id_primero]["predeterminado"] is False
