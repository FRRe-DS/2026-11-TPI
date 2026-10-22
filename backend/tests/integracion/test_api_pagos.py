import time
from decimal import Decimal
from uuid import uuid4

from app.services.integraciones import DependenciaNoDisponible, ReservaExterna
from app.services.pasarela import TARJETA_RECHAZADA, TARJETA_SIN_RESPUESTA
from tests.integracion.conftest import (
    VISA,
    WEBHOOK_SECRET,
    autorizar,
    ejecutar_sql,
    pago_capturado,
    registrar_tarjeta,
)

D = Decimal
URL = "/api/v1/pagos"


def webhook(client, pago_id, estado="aprobado", secreto=WEBHOOK_SECRET):
    headers = {"X-Webhook-Secret": secreto} if secreto else {}
    return client.post(
        f"{URL}/webhooks/pasarela",
        json={"referencia_externa": "PAS-123", "pago_id": pago_id, "estado": estado},
        headers=headers,
    )


# --- Idempotencia y doble cobro (RF-7.6, RNF-08) ----------------------------


def test_misma_idempotency_key_y_mismo_cuerpo_devuelve_el_pago_original(client, actores):
    viaje_id = uuid4()
    headers = {**actores.servicio, "Idempotency-Key": "orden-1"}

    primero = autorizar(client, actores, viaje_id=viaje_id, headers=headers)
    segundo = autorizar(client, actores, viaje_id=viaje_id, headers=headers)

    assert primero.status_code == 201
    assert segundo.status_code == 200
    assert segundo.json()["id"] == primero.json()["id"]
    assert len(client.get(URL, headers=actores.operador).json()) == 1


def test_misma_idempotency_key_con_otro_cuerpo_es_422(client, actores):
    headers = {**actores.servicio, "Idempotency-Key": "orden-1"}
    autorizar(client, actores, headers=headers)

    respuesta = autorizar(client, actores, headers=headers, monto="9999")

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["type"] == "/errores/idempotency-key-reutilizada"


def test_segundo_cobro_del_mismo_viaje_sin_clave_es_409(client, actores):
    viaje_id = uuid4()
    primero = autorizar(client, actores, viaje_id=viaje_id).json()

    respuesta = autorizar(client, actores, viaje_id=viaje_id)

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "/errores/pago-duplicado"
    assert respuesta.json()["pago_existente_id"] == primero["id"]


def test_un_cobro_rechazado_libera_el_viaje_para_reintentar(client, actores, pasarela):
    viaje_id = uuid4()
    rechazada = registrar_tarjeta(client, actores, TARJETA_RECHAZADA)
    buena = registrar_tarjeta(client, actores, VISA)

    primero = autorizar(client, actores, rechazada["id"], viaje_id=viaje_id)
    segundo = autorizar(client, actores, buena["id"], viaje_id=viaje_id)

    assert (primero.status_code, primero.json()["estado"]) == (201, "rechazado")
    assert (segundo.status_code, segundo.json()["estado"]) == (201, "autorizado")
    movimientos = client.get("/api/v1/movimientos", params={"viaje_id": str(viaje_id)}, headers=actores.operador)
    assert [m["tipo"] for m in movimientos.json()] == ["rechazo", "autorizacion"]


# --- Autorización ------------------------------------------------------------


def test_pasarela_sin_respuesta_deja_el_pago_pendiente_de_confirmacion(client, actores):
    metodo = registrar_tarjeta(client, actores, TARJETA_SIN_RESPUESTA)
    inicio = time.perf_counter()

    respuesta = autorizar(client, actores, metodo["id"])

    assert time.perf_counter() - inicio < 1, "nunca debe quedar esperando a la pasarela"
    assert (respuesta.status_code, respuesta.json()["estado"]) == (201, "pendiente_confirmacion")
    tipos = client.get("/api/v1/movimientos", params={"pago_id": respuesta.json()["id"]}, headers=actores.operador)
    assert [m["tipo"] for m in tipos.json()] == ["autorizacion_sin_respuesta"]


def test_webhook_resuelve_una_autorizacion_pendiente(client, actores):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores, TARJETA_SIN_RESPUESTA)["id"]).json()

    aprobado = webhook(client, pago["id"])
    repetido = webhook(client, pago["id"], estado="rechazado")

    assert (aprobado.status_code, aprobado.json()["estado"]) == (200, "autorizado")
    assert aprobado.json()["referencia_externa"] == "PAS-123"
    assert repetido.json()["estado"] == "autorizado"


def test_webhook_puede_rechazar_la_autorizacion(client, actores):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores, TARJETA_SIN_RESPUESTA)["id"]).json()

    assert webhook(client, pago["id"], estado="rechazado").json()["estado"] == "rechazado"


def test_webhook_requiere_el_secreto(client, actores):
    pago = autorizar(client, actores).json()

    assert webhook(client, pago["id"], secreto=None).status_code == 401
    assert webhook(client, pago["id"], secreto="otro").status_code == 401


def test_webhook_rechazado_si_no_hay_secreto_configurado(client, actores, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pasarela_webhook_secret", None)

    assert webhook(client, str(uuid4())).status_code == 401


def test_webhook_con_estado_invalido_es_400(client, actores):
    assert webhook(client, str(uuid4()), estado="reembolsado").status_code == 400


def test_metodo_de_pago_de_otro_cliente_es_422(client, actores):
    ajeno = registrar_tarjeta(client, actores, cliente_id=uuid4())

    respuesta = autorizar(client, actores, ajeno["id"])

    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/metodo-pago-invalido"


def test_metodo_de_pago_dado_de_baja_es_422(client, actores):
    metodo = registrar_tarjeta(client, actores)
    client.delete(f"/api/v1/metodos-pago/{metodo['id']}", headers=actores.cliente)

    assert autorizar(client, actores, metodo["id"]).status_code == 422


def test_estimacion_vencida_es_422(client, actores):
    estimacion = client.post(
        "/api/v1/tarifas/estimaciones",
        json={"tipo_vehiculo": "moto", "distancia_km": "5", "duracion_estimada_min": "10"},
        headers=actores.servicio,
    ).json()
    ejecutar_sql("UPDATE estimaciones SET vence_en = now() - interval '1 minute' WHERE id = :id", id=estimacion["id"])

    respuesta = autorizar(client, actores, monto=None, estimacion_id=estimacion["id"])

    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/estimacion-vencida"


def test_estimacion_inexistente_es_422(client, actores):
    respuesta = autorizar(client, actores, monto=None, estimacion_id=str(uuid4()))

    assert respuesta.json()["type"] == "/errores/estimacion-inexistente"


def test_reserva_validada_con_m9(client, actores, m9, integraciones):
    integraciones["m9"] = True
    propia, ajena = uuid4(), uuid4()
    m9.reservas[propia] = ReservaExterna(propia, actores.cliente_id, "confirmada")
    m9.reservas[ajena] = ReservaExterna(ajena, uuid4(), "confirmada")

    assert autorizar(client, actores, reserva_id=str(propia)).status_code == 201
    assert autorizar(client, actores, reserva_id=str(ajena)).json()["type"] == "/errores/reserva-de-otro-cliente"
    inexistente = autorizar(client, actores, reserva_id=str(uuid4()))
    assert inexistente.json()["type"] == "/errores/recurso-externo-inexistente"


def test_m9_caido_responde_503(client, actores, m9, integraciones):
    integraciones["m9"] = True
    m9.error = DependenciaNoDisponible("M9 Reservas")

    respuesta = autorizar(client, actores, reserva_id=str(uuid4()))

    assert respuesta.status_code == 503
    assert respuesta.json()["type"] == "/errores/dependencia-no-disponible"
    assert respuesta.headers["Retry-After"] == "5"


# --- Captura y anulación -----------------------------------------------------


def test_captura_sin_respuesta_queda_pendiente_y_no_se_repite(client, actores, pasarela):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores)["id"]).json()
    pasarela.captura_sin_respuesta = True

    primera = client.post(f"{URL}/{pago['id']}/captura", headers=actores.servicio)
    segunda = client.post(f"{URL}/{pago['id']}/captura", headers=actores.servicio)

    assert primera.json()["estado"] == "captura_pendiente"
    assert segunda.status_code == 409
    assert webhook(client, pago["id"]).json()["estado"] == "capturado"
    assert pasarela.llamadas.count("capturar") == 1


def test_webhook_puede_rechazar_la_captura(client, actores, pasarela):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores)["id"]).json()
    pasarela.captura_sin_respuesta = True
    client.post(f"{URL}/{pago['id']}/captura", headers=actores.servicio)

    rechazado = webhook(client, pago["id"], estado="rechazado").json()

    assert (rechazado["estado"], D(rechazado["monto_capturado"])) == ("rechazado", 0)


def test_no_se_captura_mas_de_lo_autorizado(client, actores):
    pago = autorizar(client, actores, monto="1000").json()

    respuesta = client.post(f"{URL}/{pago['id']}/captura", json={"monto": "1000.01"}, headers=actores.servicio)

    assert respuesta.json()["type"] == "/errores/monto-excede-autorizado"


def test_no_se_captura_dos_veces(client, actores):
    pago = pago_capturado(client, actores)

    assert client.post(f"{URL}/{pago['id']}/captura", headers=actores.servicio).status_code == 409


def test_anular_una_autorizacion(client, actores, pasarela):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores)["id"]).json()

    anulado = client.post(f"{URL}/{pago['id']}/anulacion", headers=actores.servicio)
    otra_vez = client.post(f"{URL}/{pago['id']}/anulacion", headers=actores.servicio)

    assert anulado.json()["estado"] == "anulado"
    assert otra_vez.status_code == 409
    assert "anular" in pasarela.llamadas


def test_anulacion_sin_respuesta_de_la_pasarela_es_503_y_no_cambia_el_pago(client, actores, pasarela):
    pago = autorizar(client, actores, registrar_tarjeta(client, actores)["id"]).json()
    pasarela.anulacion_sin_respuesta = True

    respuesta = client.post(f"{URL}/{pago['id']}/anulacion", headers=actores.servicio)

    assert respuesta.status_code == 503
    assert client.get(f"{URL}/{pago['id']}", headers=actores.operador).json()["estado"] == "autorizado"


# --- Reembolsos (RF-7.5) ------------------------------------------------------


def reembolsar(client, actores, pago_id, clave=None, **cuerpo):
    headers = {**actores.operador, **({"Idempotency-Key": clave} if clave else {})}
    return client.post(f"{URL}/{pago_id}/reembolsos", json={"motivo": "Demora", **cuerpo}, headers=headers)


def test_reembolso_parcial_y_luego_total(client, actores):
    pago = pago_capturado(client, actores, monto="1000", con_tarjeta=True)

    parcial = reembolsar(client, actores, pago["id"], monto="300")
    resto = reembolsar(client, actores, pago["id"])

    assert parcial.status_code == 201
    assert D(resto.json()["monto"]) == D("700")
    assert resto.json()["referencia_externa"]
    final = client.get(f"{URL}/{pago['id']}", headers=actores.operador).json()
    assert (final["estado"], D(final["monto_reembolsado"])) == ("reembolsado", D("1000"))
    listado = client.get(f"{URL}/{pago['id']}/reembolsos", headers=actores.cliente).json()
    assert [D(r["monto"]) for r in listado] == [D("300"), D("700")]


def test_reembolso_idempotente(client, actores, pasarela):
    pago = pago_capturado(client, actores, monto="1000", con_tarjeta=True)

    primero = reembolsar(client, actores, pago["id"], clave="r-1", monto="300")
    segundo = reembolsar(client, actores, pago["id"], clave="r-1", monto="300")
    otro_cuerpo = reembolsar(client, actores, pago["id"], clave="r-1", monto="400")

    assert (primero.status_code, segundo.status_code) == (201, 200)
    assert segundo.json()["id"] == primero.json()["id"]
    assert otro_cuerpo.status_code == 422
    assert pasarela.llamadas.count("reembolsar") == 1
    assert D(client.get(f"{URL}/{pago['id']}", headers=actores.operador).json()["monto_reembolsado"]) == D("300")


def test_misma_clave_en_otro_pago_es_otro_cuerpo(client, actores):
    a = pago_capturado(client, actores)
    b = pago_capturado(client, actores)
    reembolsar(client, actores, a["id"], clave="r-1", monto="10")

    assert reembolsar(client, actores, b["id"], clave="r-1", monto="10").status_code == 422


def test_reembolso_que_excede_lo_cobrado(client, actores):
    pago = pago_capturado(client, actores, monto="1000")

    respuesta = reembolsar(client, actores, pago["id"], monto="1500")

    assert respuesta.json()["type"] == "/errores/monto-excede-reembolsable"


def test_no_se_reembolsa_un_pago_no_capturado(client, actores):
    pago = autorizar(client, actores).json()

    assert reembolsar(client, actores, pago["id"]).status_code == 409


def test_reembolso_rechazado_por_la_pasarela(client, actores, pasarela):
    pago = pago_capturado(client, actores, con_tarjeta=True)
    pasarela.reembolso_rechazado = True

    respuesta = reembolsar(client, actores, pago["id"])

    assert respuesta.json()["type"] == "/errores/reembolso-rechazado"
    assert client.get(f"{URL}/{pago['id']}", headers=actores.operador).json()["estado"] == "capturado"


def test_el_cliente_no_puede_reembolsarse(client, actores):
    pago = pago_capturado(client, actores)

    respuesta = client.post(f"{URL}/{pago['id']}/reembolsos", json={"motivo": "x"}, headers=actores.cliente)

    assert respuesta.status_code == 403


# --- Consultas ---------------------------------------------------------------


def test_listar_pagos_con_filtros(client, actores):
    viaje_id = uuid4()
    autorizar(client, actores, viaje_id=viaje_id)
    pago_capturado(client, actores)

    assert len(client.get(URL, params={"viaje_id": str(viaje_id)}, headers=actores.operador).json()) == 1
    assert len(client.get(URL, params={"estado": "capturado"}, headers=actores.operador).json()) == 1
    assert len(client.get(URL, params={"tipo_operacion": "cobro_viaje"}, headers=actores.operador).json()) == 2


def test_pago_inexistente_es_404(client, actores):
    respuesta = client.get(f"{URL}/{uuid4()}", headers=actores.operador)

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "about:blank"
