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
