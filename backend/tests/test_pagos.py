from decimal import Decimal
from uuid import uuid4

from tests.conftest import WEBHOOK_SECRET, nuevo_pago

URL = "/api/v1/pagos"


def webhook(client, pago_id, estado="aprobado", secreto=WEBHOOK_SECRET):
    headers = {"X-Webhook-Secret": secreto} if secreto else {}
    return client.post(
        f"{URL}/webhooks/pasarela",
        json={"referencia_externa": "PAS-123", "pago_id": pago_id, "estado": estado},
        headers=headers,
    )


# --- Creación ---------------------------------------------------------------


def test_pago_en_efectivo_queda_aprobado(client):
    pago = nuevo_pago(client, metodo="efectivo")

    assert pago["estado"] == "aprobado"
    assert pago["moneda"] == "ARS"
    assert Decimal(pago["monto_reembolsado"]) == 0


def test_pago_con_tarjeta_queda_pendiente_de_pasarela(client):
    assert nuevo_pago(client, metodo="tarjeta")["estado"] == "pendiente"


def test_pago_rechaza_monto_no_positivo(client):
    respuesta = client.post(
        URL,
        json={
            "viaje_id": str(uuid4()),
            "cliente_id": str(uuid4()),
            "beneficiario_id": str(uuid4()),
            "monto": "0",
            "metodo": "efectivo",
        },
    )

    assert respuesta.status_code == 422


def test_pago_rechaza_metodo_desconocido(client):
    respuesta = client.post(
        URL,
        json={
            "viaje_id": str(uuid4()),
            "cliente_id": str(uuid4()),
            "beneficiario_id": str(uuid4()),
            "monto": "100",
            "metodo": "cheque",
        },
    )

    assert respuesta.status_code == 422


# --- Idempotencia (RF-7.6) --------------------------------------------------


def test_misma_idempotency_key_devuelve_el_pago_original(client):
    headers = {"Idempotency-Key": "orden-1"}
    cuerpo = {
        "viaje_id": str(uuid4()),
        "cliente_id": str(uuid4()),
        "beneficiario_id": str(uuid4()),
        "monto": "1000",
        "metodo": "efectivo",
    }

    primero = client.post(URL, json=cuerpo, headers=headers)
    segundo = client.post(URL, json=cuerpo, headers=headers)

    assert primero.status_code == 201
    assert segundo.status_code == 200
    assert segundo.json()["id"] == primero.json()["id"]
    assert len(client.get(URL).json()) == 1


def test_idempotency_keys_distintas_crean_pagos_distintos(client):
    a = nuevo_pago(client, headers={"Idempotency-Key": "a"})
    b = nuevo_pago(client, headers={"Idempotency-Key": "b"})

    assert a["id"] != b["id"]


def test_sin_idempotency_key_cada_pedido_crea_un_pago(client):
    nuevo_pago(client)
    nuevo_pago(client)

    assert len(client.get(URL).json()) == 2


# --- Consultas --------------------------------------------------------------


def test_obtener_pago_por_id(client):
    pago = nuevo_pago(client)

    assert client.get(f"{URL}/{pago['id']}").json() == pago


def test_pago_inexistente_devuelve_404(client):
    assert client.get(f"{URL}/{uuid4()}").status_code == 404


def test_listar_pagos_filtra_por_beneficiario_cliente_y_estado(client):
    chofer = uuid4()
    pasajero = uuid4()
    nuevo_pago(client, beneficiario_id=chofer, cliente_id=pasajero, metodo="efectivo")
    nuevo_pago(client, beneficiario_id=chofer, metodo="tarjeta")
    nuevo_pago(client)

    assert len(client.get(URL, params={"beneficiario_id": str(chofer)}).json()) == 2
    assert len(client.get(URL, params={"cliente_id": str(pasajero)}).json()) == 1
    pendientes = client.get(URL, params={"beneficiario_id": str(chofer), "estado": "pendiente"}).json()
    assert [p["metodo"] for p in pendientes] == ["tarjeta"]


# --- Reembolsos (RF-7.5) ----------------------------------------------------


def test_reembolso_parcial(client):
    pago = nuevo_pago(client, monto="1000")

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "300", "motivo": "Demora"})

    assert respuesta.status_code == 201
    assert Decimal(respuesta.json()["monto"]) == Decimal("300")
    actualizado = client.get(f"{URL}/{pago['id']}").json()
    assert actualizado["estado"] == "reembolsado_parcial"
    assert Decimal(actualizado["monto_reembolsado"]) == Decimal("300")


def test_reembolso_sin_monto_devuelve_el_saldo_restante(client):
    pago = nuevo_pago(client, monto="1000")
    client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "300", "motivo": "Demora"})

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"motivo": "Cancelación"})

    assert Decimal(respuesta.json()["monto"]) == Decimal("700")
    assert client.get(f"{URL}/{pago['id']}").json()["estado"] == "reembolsado"


def test_reembolso_no_puede_superar_lo_cobrado(client):
    pago = nuevo_pago(client, monto="1000")

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "1500", "motivo": "Error"})

    assert respuesta.status_code == 422
    assert client.get(f"{URL}/{pago['id']}").json()["estado"] == "aprobado"


def test_no_se_reembolsa_un_pago_ya_reembolsado(client):
    pago = nuevo_pago(client, monto="1000")
    client.post(f"{URL}/{pago['id']}/reembolsos", json={"motivo": "Cancelación"})

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "1", "motivo": "Otra vez"})

    assert respuesta.status_code == 409


def test_no_se_reembolsa_un_pago_pendiente(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"motivo": "Cancelación"})

    assert respuesta.status_code == 409


def test_reembolso_requiere_motivo(client):
    pago = nuevo_pago(client)

    assert client.post(f"{URL}/{pago['id']}/reembolsos", json={"motivo": ""}).status_code == 422


def test_listar_reembolsos_de_un_pago(client):
    pago = nuevo_pago(client, monto="1000")
    client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "100", "motivo": "A"})
    client.post(f"{URL}/{pago['id']}/reembolsos", json={"monto": "200", "motivo": "B"})

    reembolsos = client.get(f"{URL}/{pago['id']}/reembolsos").json()

    assert [r["motivo"] for r in reembolsos] == ["A", "B"]


def test_reembolsos_de_pago_inexistente_devuelve_404(client):
    assert client.get(f"{URL}/{uuid4()}/reembolsos").status_code == 404
    assert client.post(f"{URL}/{uuid4()}/reembolsos", json={"motivo": "x"}).status_code == 404


# --- Webhook de la pasarela -------------------------------------------------


def test_webhook_aprueba_un_pago_pendiente(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    respuesta = webhook(client, pago["id"])

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aprobado"
    assert respuesta.json()["referencia_externa"] == "PAS-123"


def test_webhook_rechaza_un_pago_pendiente(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    assert webhook(client, pago["id"], estado="rechazado").json()["estado"] == "rechazado"


def test_webhook_repetido_no_cambia_el_pago(client):
    pago = nuevo_pago(client, metodo="tarjeta")
    webhook(client, pago["id"], estado="aprobado")

    respuesta = webhook(client, pago["id"], estado="rechazado")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aprobado"


def test_webhook_con_estado_no_valido_devuelve_422(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    assert webhook(client, pago["id"], estado="reembolsado").status_code == 422


def test_webhook_sin_secreto_devuelve_401(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    assert webhook(client, pago["id"], secreto=None).status_code == 401


def test_webhook_con_secreto_incorrecto_devuelve_401(client):
    pago = nuevo_pago(client, metodo="tarjeta")

    assert webhook(client, pago["id"], secreto="otro").status_code == 401
    assert client.get(f"{URL}/{pago['id']}").json()["estado"] == "pendiente"


def test_webhook_rechazado_si_no_hay_secreto_configurado(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pasarela_webhook_secret", None)
    pago = nuevo_pago(client, metodo="tarjeta")

    assert webhook(client, pago["id"]).status_code == 401
