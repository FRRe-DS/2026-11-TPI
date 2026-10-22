"""401 sin token o con token inválido, 403 por scope, por rol y por propiedad."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.integracion.conftest import autorizar, pago_capturado

PROTEGIDAS = [
    ("get", "/api/v1/tarifas/reglas"),
    ("post", "/api/v1/tarifas/estimaciones"),
    ("get", "/api/v1/pagos"),
    ("post", "/api/v1/pagos"),
    ("get", "/api/v1/metodos-pago"),
    ("post", "/api/v1/cancelaciones"),
    ("get", "/api/v1/liquidaciones"),
    ("get", "/api/v1/movimientos"),
]


@pytest.mark.parametrize(("metodo", "ruta"), PROTEGIDAS)
def test_sin_token_es_401_en_problem_json(client, metodo, ruta):
    respuesta = getattr(client, metodo)(ruta)

    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"
    assert respuesta.json()["type"] == "about:blank"
    assert respuesta.json()["title"] == "No autenticado"


def test_token_vencido_es_401(client, emitir_token):
    token = emitir_token(roles=("operador",), vence_en=timedelta(seconds=-5))

    respuesta = client.get("/api/v1/pagos", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_token_para_otra_audiencia_es_401(client, emitir_token):
    token = emitir_token(roles=("operador",), aud="m2-clientes")

    assert client.get("/api/v1/pagos", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_falta_de_scope_es_403(client, actores):
    headers = actores.headers("operador", scopes="tarifas:read")

    respuesta = client.get("/api/v1/pagos", headers=headers)

    assert respuesta.status_code == 403
    assert respuesta.json()["title"] == "Sin permiso"
    assert "pagos:read" in respuesta.json()["detail"]
    assert client.get("/api/v1/tarifas/reglas", headers=headers).status_code == 200


def test_scope_de_lectura_no_habilita_escritura(client, actores):
    headers = actores.headers("cliente", sub=actores.cliente_id, scopes="pagos:read")

    assert autorizar(client, actores, headers=headers).status_code == 403


def test_token_sin_rol_de_m7_es_403(client, actores):
    assert client.get("/api/v1/pagos", headers=actores.headers("offline_access")).status_code == 403


def test_roles_en_mayusculas_como_en_el_contrato_de_m2(client, actores):
    assert client.get("/api/v1/pagos", headers=actores.headers("OPERADOR")).status_code == 200


def test_cliente_crea_pagos_solo_para_si(client, actores):
    assert autorizar(client, actores, headers=actores.cliente).status_code == 201
    otro = actores.headers("cliente")
    assert autorizar(client, actores, headers=otro).status_code == 403


def test_conductor_no_crea_pagos(client, actores):
    assert autorizar(client, actores, headers=actores.conductor).status_code == 403


def test_cliente_no_captura_ni_anula(client, actores):
    pago = autorizar(client, actores).json()

    assert client.post(f"/api/v1/pagos/{pago['id']}/captura", headers=actores.cliente).status_code == 403
    assert client.post(f"/api/v1/pagos/{pago['id']}/anulacion", headers=actores.cliente).status_code == 403


def test_cada_rol_ve_solo_sus_pagos(client, actores):
    propio = pago_capturado(client, actores)
    ajeno = autorizar(client, actores, cliente_id=str(uuid4()), beneficiario_id=str(uuid4())).json()

    assert [p["id"] for p in client.get("/api/v1/pagos", headers=actores.cliente).json()] == [propio["id"]]
    assert [p["id"] for p in client.get("/api/v1/pagos", headers=actores.conductor).json()] == [propio["id"]]
    assert len(client.get("/api/v1/pagos", headers=actores.operador).json()) == 2
    assert len(client.get("/api/v1/pagos", headers=actores.servicio).json()) == 2

    assert client.get(f"/api/v1/pagos/{propio['id']}", headers=actores.conductor).status_code == 200
    assert client.get(f"/api/v1/pagos/{ajeno['id']}", headers=actores.cliente).status_code == 403
    assert client.get(f"/api/v1/pagos/{ajeno['id']}/reembolsos", headers=actores.cliente).status_code == 403
    pedido_ajeno = client.get("/api/v1/pagos", params={"cliente_id": ajeno["cliente_id"]}, headers=actores.cliente)
    assert pedido_ajeno.status_code == 403


def test_movimientos_filtrados_por_rol(client, actores):
    pago_capturado(client, actores)
    autorizar(client, actores, cliente_id=str(uuid4()), beneficiario_id=str(uuid4()))

    del_cliente = client.get("/api/v1/movimientos", headers=actores.cliente).json()
    del_conductor = client.get("/api/v1/movimientos", headers=actores.conductor).json()
    todos = client.get("/api/v1/movimientos", headers=actores.operador).json()

    assert {m["cliente_id"] for m in del_cliente} == {str(actores.cliente_id)}
    assert {m["beneficiario_id"] for m in del_conductor} == {str(actores.conductor_id)}
    assert len(todos) == 3
    assert client.get("/api/v1/movimientos", params={"tipo": "captura"}, headers=actores.operador).json()[0]["actor"]
