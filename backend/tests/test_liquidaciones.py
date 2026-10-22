from decimal import Decimal
from uuid import uuid4

from tests.conftest import nuevo_pago

URL = "/api/v1/liquidaciones"


def liquidar(client, beneficiario_id, desde, hasta=None):
    return client.post(
        URL,
        json={"beneficiario_id": str(beneficiario_id), "periodo_desde": desde, "periodo_hasta": hasta or desde},
    )


def test_liquidacion_descuenta_comision_de_la_plataforma(client, hoy):
    chofer = uuid4()
    a = nuevo_pago(client, monto="1000", beneficiario_id=chofer)
    b = nuevo_pago(client, monto="500", beneficiario_id=chofer)

    respuesta = liquidar(client, chofer, hoy)

    assert respuesta.status_code == 201
    liq = respuesta.json()
    assert sorted(liq["pago_ids"]) == sorted([a["id"], b["id"]])
    assert Decimal(liq["monto_bruto"]) == Decimal("1500")
    assert Decimal(liq["comision_plataforma"]) == Decimal("300")
    assert Decimal(liq["monto_neto"]) == Decimal("1200")
    assert liq["estado"] == "pendiente"


def test_liquidacion_descuenta_reembolsos_parciales(client, hoy):
    chofer = uuid4()
    pago = nuevo_pago(client, monto="1000", beneficiario_id=chofer)
    client.post(f"/api/v1/pagos/{pago['id']}/reembolsos", json={"monto": "400", "motivo": "Demora"})

    liq = liquidar(client, chofer, hoy).json()

    assert Decimal(liq["monto_bruto"]) == Decimal("600")


def test_liquidacion_ignora_pagos_no_cobrados_y_de_otros_beneficiarios(client, hoy):
    chofer = uuid4()
    cobrado = nuevo_pago(client, beneficiario_id=chofer)
    nuevo_pago(client, beneficiario_id=chofer, metodo="tarjeta")  # pendiente
    reembolsado = nuevo_pago(client, beneficiario_id=chofer)
    client.post(f"/api/v1/pagos/{reembolsado['id']}/reembolsos", json={"motivo": "Cancelación"})
    nuevo_pago(client)  # otro chofer

    liq = liquidar(client, chofer, hoy).json()

    assert liq["pago_ids"] == [cobrado["id"]]


def test_liquidacion_fuera_del_periodo_devuelve_422(client):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)

    assert liquidar(client, chofer, "2000-01-01", "2000-01-31").status_code == 422


def test_liquidacion_sin_pagos_devuelve_422(client, hoy):
    assert liquidar(client, uuid4(), hoy).status_code == 422


def test_liquidacion_con_periodo_invertido_devuelve_422(client):
    assert liquidar(client, uuid4(), "2026-02-01", "2026-01-01").status_code == 422


def test_un_pago_no_se_liquida_dos_veces(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liquidar(client, chofer, hoy)

    assert liquidar(client, chofer, hoy).status_code == 422


def test_confirmar_transferencia(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liq = liquidar(client, chofer, hoy).json()

    respuesta = client.post(f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "CBU-999"})

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "transferida"
    assert respuesta.json()["referencia_transferencia"] == "CBU-999"


def test_no_se_transfiere_dos_veces(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liq = liquidar(client, chofer, hoy).json()
    client.post(f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "CBU-1"})

    respuesta = client.post(f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "CBU-2"})

    assert respuesta.status_code == 409


def test_no_se_anula_una_liquidacion_transferida(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liq = liquidar(client, chofer, hoy).json()
    client.post(f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "CBU-1"})

    assert client.post(f"{URL}/{liq['id']}/anulacion").status_code == 409


def test_anular_libera_los_pagos_para_una_nueva_liquidacion(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liq = liquidar(client, chofer, hoy).json()

    anulada = client.post(f"{URL}/{liq['id']}/anulacion")
    nueva = liquidar(client, chofer, hoy)

    assert anulada.json()["estado"] == "anulada"
    assert nueva.status_code == 201
    assert nueva.json()["pago_ids"] == liq["pago_ids"]


def test_listar_y_obtener_liquidaciones(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, beneficiario_id=chofer)
    liq = liquidar(client, chofer, hoy).json()

    assert client.get(f"{URL}/{liq['id']}").json() == liq
    assert client.get(URL, params={"beneficiario_id": str(chofer)}).json() == [liq]
    assert client.get(URL, params={"estado": "transferida"}).json() == []


def test_liquidacion_inexistente_devuelve_404(client):
    assert client.get(f"{URL}/{uuid4()}").status_code == 404
    assert client.post(f"{URL}/{uuid4()}/anulacion").status_code == 404


def test_saldo_del_beneficiario(client, hoy):
    chofer = uuid4()
    nuevo_pago(client, monto="1000", beneficiario_id=chofer)
    liq_transferida = liquidar(client, chofer, hoy).json()
    client.post(f"{URL}/{liq_transferida['id']}/transferencia", json={"referencia_transferencia": "CBU-1"})
    nuevo_pago(client, monto="500", beneficiario_id=chofer)
    liquidar(client, chofer, hoy)
    nuevo_pago(client, monto="200", beneficiario_id=chofer)

    saldo = client.get(f"{URL}/saldos/{chofer}").json()

    assert Decimal(saldo["saldo_pendiente_liquidar"]) == Decimal("200")
    assert Decimal(saldo["liquidado_pendiente_transferir"]) == Decimal("400")
    assert Decimal(saldo["total_transferido"]) == Decimal("800")


def test_saldo_de_beneficiario_sin_movimientos_es_cero(client):
    saldo = client.get(f"{URL}/saldos/{uuid4()}").json()

    assert Decimal(saldo["saldo_pendiente_liquidar"]) == 0
    assert Decimal(saldo["total_transferido"]) == 0
