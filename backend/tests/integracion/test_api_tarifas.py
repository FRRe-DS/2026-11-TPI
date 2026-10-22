from decimal import Decimal
from uuid import uuid4

from app.services.integraciones import DependenciaNoDisponible, RutaEstimada

D = Decimal
URL = "/api/v1/tarifas"
REGLA = {
    "tipo_vehiculo": "auto",
    "tarifa_base": "1000",
    "precio_por_km": "500",
    "precio_por_minuto": "70",
    "tarifa_minima": "2500",
}


def estimar(client, headers, **datos):
    cuerpo = {"tipo_vehiculo": "auto", "distancia_km": "10", "duracion_estimada_min": "20", **datos}
    return client.post(f"{URL}/estimaciones", json=cuerpo, headers=headers)


def regla_activa(client, headers, tipo="auto"):
    reglas = client.get(f"{URL}/reglas", params={"tipo_vehiculo": tipo, "solo_activas": True}, headers=headers).json()
    assert len(reglas) == 1
    return reglas[0]


def test_estimacion_queda_guardada_con_vencimiento(client, actores):
    creada = estimar(client, actores.cliente).json()

    consultada = client.get(f"{URL}/estimaciones/{creada['id']}", headers=actores.servicio).json()

    assert consultada == creada
    assert consultada["vigente"] is True
    assert consultada["vence_en"] > consultada["creada_en"]
    assert consultada["regla_id"] == regla_activa(client, actores.cliente)["id"]


def test_estimacion_con_origen_y_destino_consulta_a_m4(client, actores, m4, integraciones):
    integraciones["m4"] = True
    m4.ruta = RutaEstimada(D("4"), D("8"))
    puntos = {"origen": {"lat": -27.45, "lng": -58.98}, "destino": {"lat": -27.47, "lng": -58.83}}

    respuesta = estimar(
        client, actores.cliente, distancia_km=None, duracion_estimada_min=None, tipo_vehiculo="moto", **puntos
    )

    # moto: 500 + 250*4 + 40*8 = 1820
    assert D(respuesta.json()["desglose"]["total"]) == D("1820")
    assert (D(respuesta.json()["distancia_km"]), m4.consultas) == (D("4"), 1)


def test_estimacion_con_distancia_no_consulta_a_m4(client, actores, m4, integraciones):
    integraciones["m4"] = True

    estimar(client, actores.cliente)

    assert m4.consultas == 0


def test_sin_m4_hay_que_enviar_distancia(client, actores):
    puntos = {"origen": {"lat": 0, "lng": 0}, "destino": {"lat": 1, "lng": 1}}

    respuesta = estimar(client, actores.cliente, distancia_km=None, duracion_estimada_min=None, **puntos)

    assert respuesta.json()["type"] == "/errores/ruta-no-disponible"


def test_m4_caido_responde_503(client, actores, m4, integraciones):
    integraciones["m4"] = True
    m4.error = DependenciaNoDisponible("M4 Ubicación")
    puntos = {"origen": {"lat": 0, "lng": 0}, "destino": {"lat": 1, "lng": 1}}

    respuesta = estimar(client, actores.cliente, distancia_km=None, duracion_estimada_min=None, **puntos)

    assert respuesta.status_code == 503


def test_estimacion_inexistente_es_404(client, actores):
    assert client.get(f"{URL}/estimaciones/{uuid4()}", headers=actores.cliente).status_code == 404


def test_sin_regla_activa_es_422(client, actores):
    regla = regla_activa(client, actores.operador)
    client.patch(f"{URL}/reglas/{regla['id']}", json={"activa": False}, headers=actores.operador)

    assert estimar(client, actores.cliente).json()["type"] == "/errores/sin-regla-activa"


def test_tarifa_final_una_sola_vez(client, actores):
    viaje_id = uuid4()
    cuerpo = {"tipo_vehiculo": "auto", "distancia_real_km": "10", "duracion_real_min": "20"}

    creada = client.post(f"{URL}/viajes/{viaje_id}/tarifa-final", json=cuerpo, headers=actores.servicio)
    repetida = client.post(f"{URL}/viajes/{viaje_id}/tarifa-final", json=cuerpo, headers=actores.servicio)

    assert creada.status_code == 201
    assert repetida.json()["type"] == "/errores/tarifa-final-existente"
    assert client.get(f"{URL}/viajes/{viaje_id}/tarifa-final", headers=actores.cliente).json() == creada.json()
    assert client.get(f"{URL}/viajes/{uuid4()}/tarifa-final", headers=actores.cliente).status_code == 404


def test_un_cliente_no_registra_tarifas_finales(client, actores):
    cuerpo = {"tipo_vehiculo": "auto", "distancia_real_km": "1", "duracion_real_min": "1"}

    assert client.post(f"{URL}/viajes/{uuid4()}/tarifa-final", json=cuerpo, headers=actores.cliente).status_code == 403


def test_reglas_iniciales_solo_auto_y_moto(client, actores):
    reglas = client.get(f"{URL}/reglas", headers=actores.cliente).json()

    assert sorted(r["tipo_vehiculo"] for r in reglas) == ["auto", "moto"]


def test_crear_regla_activa_reemplaza_la_vigente(client, actores):
    anterior = regla_activa(client, actores.operador)

    nueva = client.post(f"{URL}/reglas", json=REGLA, headers=actores.operador)

    assert nueva.status_code == 201
    assert regla_activa(client, actores.operador)["id"] == nueva.json()["id"]
    assert client.get(f"{URL}/reglas/{anterior['id']}", headers=actores.operador).json()["activa"] is False


def test_reactivar_una_regla_desactiva_la_vigente(client, actores):
    vieja = regla_activa(client, actores.operador)
    nueva = client.post(f"{URL}/reglas", json=REGLA, headers=actores.operador).json()

    respuesta = client.patch(
        f"{URL}/reglas/{vieja['id']}", json={"activa": True, "precio_por_km": "460"}, headers=actores.operador
    )

    assert D(respuesta.json()["precio_por_km"]) == D("460")
    assert regla_activa(client, actores.operador)["id"] == vieja["id"]
    assert client.get(f"{URL}/reglas/{nueva['id']}", headers=actores.operador).json()["activa"] is False


def test_crear_regla_inactiva_no_toca_la_vigente(client, actores):
    vigente = regla_activa(client, actores.operador)

    client.post(f"{URL}/reglas", json={**REGLA, "activa": False}, headers=actores.operador)

    assert regla_activa(client, actores.operador)["id"] == vigente["id"]


def test_solo_el_operador_administra_reglas(client, actores):
    regla = regla_activa(client, actores.operador)

    for headers in (actores.cliente, actores.conductor, actores.servicio):
        assert client.post(f"{URL}/reglas", json=REGLA, headers=headers).status_code == 403
        assert client.patch(f"{URL}/reglas/{regla['id']}", json={"activa": False}, headers=headers).status_code == 403


def test_regla_inexistente_es_404(client, actores):
    assert client.get(f"{URL}/reglas/{uuid4()}", headers=actores.operador).status_code == 404
    assert client.patch(f"{URL}/reglas/{uuid4()}", json={}, headers=actores.operador).status_code == 404
