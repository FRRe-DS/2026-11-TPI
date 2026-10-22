from uuid import uuid4

from tests.integracion.conftest import VISA, ejecutar_sql

URL = "/api/v1/metodos-pago"


def alta(client, headers, cliente_id, **datos):
    return client.post(URL, json={"cliente_id": str(cliente_id), **datos}, headers=headers)


def test_tarjeta_guarda_solo_marca_ultimos_4_y_token(client, actores):
    respuesta = alta(client, actores.cliente, actores.cliente_id, tipo="tarjeta", numero_tarjeta=VISA, alias="Mi visa")

    assert respuesta.status_code == 201
    metodo = respuesta.json()
    assert (metodo["marca"], metodo["ultimos_4"], metodo["alias"]) == ("visa", "1111", "Mi visa")
    assert respuesta.headers["Location"] == f"{URL}/{metodo['id']}"
    assert "numero_tarjeta" not in metodo and "token_pasarela" not in metodo
    assert VISA not in respuesta.text
    fila = ejecutar_sql("SELECT * FROM metodos_pago").mappings().one()
    assert VISA not in str(dict(fila))
    assert fila["token_pasarela"].startswith("tok_sim_")


def test_no_acepta_cvv(client, actores):
    respuesta = alta(client, actores.cliente, actores.cliente_id, tipo="tarjeta", numero_tarjeta=VISA, cvv="123")

    assert respuesta.status_code == 400
    assert ejecutar_sql("SELECT count(*) FROM metodos_pago").scalar() == 0


def test_billetera_virtual_y_efectivo(client, actores):
    billetera = alta(client, actores.cliente, actores.cliente_id, tipo="billetera_virtual", proveedor="mercadopago")
    efectivo = alta(client, actores.cliente, actores.cliente_id, tipo="efectivo")

    assert (billetera.json()["marca"], billetera.json()["ultimos_4"]) == ("mercadopago", None)
    assert efectivo.json()["tipo"] == "efectivo"


def test_un_cliente_no_registra_medios_para_otro(client, actores):
    assert alta(client, actores.cliente, uuid4(), tipo="efectivo").status_code == 403


def test_un_conductor_no_registra_medios_de_pago(client, actores):
    assert alta(client, actores.conductor, actores.conductor_id, tipo="efectivo").status_code == 403


def test_listado_por_cliente_y_baja_logica(client, actores):
    propio = alta(client, actores.cliente, actores.cliente_id, tipo="tarjeta", numero_tarjeta=VISA).json()
    alta(client, actores.operador, uuid4(), tipo="efectivo")

    assert [m["id"] for m in client.get(URL, headers=actores.cliente).json()] == [propio["id"]]
    assert len(client.get(URL, headers=actores.operador).json()) == 2

    assert client.delete(f"{URL}/{propio['id']}", headers=actores.cliente).status_code == 204
    assert client.delete(f"{URL}/{propio['id']}", headers=actores.cliente).status_code == 204
    assert client.get(URL, headers=actores.cliente).json() == []
    con_bajas = client.get(URL, params={"incluir_bajas": True}, headers=actores.cliente).json()
    assert con_bajas[0]["activo"] is False and con_bajas[0]["eliminado_en"]


def test_un_cliente_no_ve_ni_borra_medios_ajenos(client, actores):
    ajeno = alta(client, actores.operador, uuid4(), tipo="efectivo").json()

    assert client.get(f"{URL}/{ajeno['id']}", headers=actores.cliente).status_code == 403
    assert client.delete(f"{URL}/{ajeno['id']}", headers=actores.cliente).status_code == 403
    assert client.get(URL, params={"cliente_id": ajeno["cliente_id"]}, headers=actores.cliente).status_code == 403
    assert client.get(f"{URL}/{ajeno['id']}", headers=actores.operador).status_code == 200


def test_medio_inexistente_es_404(client, actores):
    assert client.get(f"{URL}/{uuid4()}", headers=actores.operador).status_code == 404
