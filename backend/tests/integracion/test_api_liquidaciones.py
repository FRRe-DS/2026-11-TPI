from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from tests.integracion.conftest import autorizar, pago_capturado

D = Decimal
URL = "/api/v1/liquidaciones"


def hoy() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def liquidar(client, actores, desde=None, hasta=None, beneficiario_id=None):
    cuerpo = {
        "beneficiario_id": str(beneficiario_id or actores.conductor_id),
        "periodo_desde": desde or hoy(),
        "periodo_hasta": hasta or desde or hoy(),
    }
    return client.post(URL, json=cuerpo, headers=actores.operador)


def test_comision_configurable(client, actores, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "comision_plataforma", D("0.10"))
    pago_capturado(client, actores, monto="1000")

    liq = liquidar(client, actores).json()

    assert (D(liq["comision_porcentaje"]), D(liq["monto_neto"])) == (D("0.10"), D("900"))


def test_descuenta_reembolsos_e_ignora_pagos_no_cobrados(client, actores):
    pago = pago_capturado(client, actores, monto="1000")
    client.post(
        f"/api/v1/pagos/{pago['id']}/reembolsos", json={"monto": "400", "motivo": "x"}, headers=actores.operador
    )
    autorizar(client, actores)  # autorizado, todavía no cobrado

    liq = liquidar(client, actores).json()

    assert liq["pago_ids"] == [pago["id"]]
    assert D(liq["monto_bruto"]) == D("600")


def test_un_pago_no_se_liquida_dos_veces(client, actores):
    pago_capturado(client, actores)
    liquidar(client, actores)

    respuesta = liquidar(client, actores)

    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/sin-pagos-para-liquidar"


def test_periodo_sin_pagos(client, actores):
    pago_capturado(client, actores)

    assert liquidar(client, actores, "2000-01-01", "2000-01-31").status_code == 422


def test_periodo_invertido_es_400(client, actores):
    assert liquidar(client, actores, "2026-02-01", "2026-01-01").status_code == 400


def test_anular_libera_los_pagos(client, actores):
    pago_capturado(client, actores)
    liq = liquidar(client, actores).json()

    anulada = client.post(f"{URL}/{liq['id']}/anulacion", headers=actores.operador)
    nueva = liquidar(client, actores)

    assert anulada.json()["estado"] == "anulada"
    assert anulada.json()["pago_ids"] == liq["pago_ids"], "la liquidación anulada conserva su historial"
    assert nueva.json()["pago_ids"] == liq["pago_ids"]


def test_transiciones_de_liquidacion(client, actores):
    pago_capturado(client, actores)
    liq = liquidar(client, actores).json()
    transferir = {"referencia_transferencia": "CBU-1"}

    assert client.post(f"{URL}/{liq['id']}/transferencia", json=transferir, headers=actores.operador).status_code == 200
    assert client.post(f"{URL}/{liq['id']}/transferencia", json=transferir, headers=actores.operador).status_code == 409
    assert client.post(f"{URL}/{liq['id']}/anulacion", headers=actores.operador).status_code == 409


def test_solo_el_operador_confirma_o_anula(client, actores):
    pago_capturado(client, actores)
    liq = liquidar(client, actores).json()

    for headers in (actores.conductor, actores.servicio, actores.cliente):
        transferencia = client.post(
            f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "x"}, headers=headers
        )
        assert transferencia.status_code == 403
        assert client.post(f"{URL}/{liq['id']}/anulacion", headers=headers).status_code == 403


def test_el_servicio_puede_generar_liquidaciones(client, actores):
    pago_capturado(client, actores)
    cuerpo = {"beneficiario_id": str(actores.conductor_id), "periodo_desde": hoy(), "periodo_hasta": hoy()}

    assert client.post(URL, json=cuerpo, headers=actores.servicio).status_code == 201
    assert client.post(URL, json=cuerpo, headers=actores.conductor).status_code == 403


def test_el_conductor_solo_ve_lo_suyo(client, actores):
    pago_capturado(client, actores)
    propia = liquidar(client, actores).json()
    ajeno = uuid4()

    assert [x["id"] for x in client.get(URL, headers=actores.conductor).json()] == [propia["id"]]
    assert client.get(f"{URL}/{propia['id']}", headers=actores.conductor).status_code == 200
    assert client.get(URL, params={"beneficiario_id": str(ajeno)}, headers=actores.conductor).status_code == 403
    assert client.get(f"{URL}/saldos/{ajeno}", headers=actores.conductor).status_code == 403
    assert client.get(f"{URL}/{propia['id']}", headers=actores.headers("conductor")).status_code == 403
    assert client.get(URL, params={"estado": "pendiente"}, headers=actores.operador).json()[0]["id"] == propia["id"]


def test_saldo_del_beneficiario(client, actores):
    pago_capturado(client, actores, monto="1000")
    liq = liquidar(client, actores).json()
    client.post(f"{URL}/{liq['id']}/transferencia", json={"referencia_transferencia": "CBU"}, headers=actores.operador)
    pago_capturado(client, actores, monto="500")
    liquidar(client, actores)
    pago_capturado(client, actores, monto="200")

    saldo = client.get(f"{URL}/saldos/{actores.conductor_id}", headers=actores.conductor).json()

    assert D(saldo["saldo_pendiente_liquidar"]) == D("200")
    assert D(saldo["liquidado_pendiente_transferir"]) == D("400")
    assert D(saldo["total_transferido"]) == D("800")


def test_liquidacion_inexistente_es_404(client, actores):
    assert client.get(f"{URL}/{uuid4()}", headers=actores.operador).status_code == 404
