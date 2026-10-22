from decimal import Decimal
from uuid import uuid4

URL = "/api/v1/tarifas"


def estimar(client, **datos):
    cuerpo = {"tipo_vehiculo": "auto", "distancia_km": "10", "duracion_estimada_min": "20", **datos}
    return client.post(f"{URL}/estimaciones", json=cuerpo)


def regla_activa(client, tipo):
    reglas = client.get(f"{URL}/reglas", params={"tipo_vehiculo": tipo, "solo_activas": True}).json()
    assert len(reglas) == 1
    return reglas[0]


# --- Estimaciones -----------------------------------------------------------


def test_estimacion_auto_suma_base_distancia_y_tiempo(client):
    # Regla inicial auto: base 900, 450/km, 60/min
    respuesta = estimar(client)

    assert respuesta.status_code == 200
    desglose = respuesta.json()["desglose"]
    assert Decimal(desglose["tarifa_base"]) == Decimal("900")
    assert Decimal(desglose["cargo_distancia"]) == Decimal("4500")
    assert Decimal(desglose["cargo_tiempo"]) == Decimal("1200")
    assert Decimal(desglose["total"]) == Decimal("6600")


def test_estimacion_aplica_multiplicador_de_demanda(client):
    respuesta = estimar(client, multiplicador_demanda="1.5")

    assert Decimal(respuesta.json()["desglose"]["total"]) == Decimal("9900")


def test_estimacion_respeta_tarifa_minima(client):
    # Moto: 500 + 250 + 40 = 790, por debajo de la mínima de 1200
    respuesta = estimar(client, tipo_vehiculo="moto", distancia_km="1", duracion_estimada_min="1")

    assert Decimal(respuesta.json()["desglose"]["total"]) == Decimal("1200")


def test_estimacion_redondea_a_centavos(client):
    respuesta = estimar(client, distancia_km="10.333")

    # 900 + 4649.85 + 1200 = 6749.85
    assert Decimal(respuesta.json()["desglose"]["total"]) == Decimal("6749.85")


def test_estimacion_informa_la_regla_usada(client):
    respuesta = estimar(client)

    assert respuesta.json()["regla_id"] == regla_activa(client, "auto")["id"]
    assert respuesta.json()["moneda"] == "ARS"


def test_estimacion_rechaza_multiplicador_menor_a_uno(client):
    assert estimar(client, multiplicador_demanda="0.5").status_code == 422


def test_estimacion_rechaza_distancia_no_positiva(client):
    assert estimar(client, distancia_km="0").status_code == 422


def test_estimacion_rechaza_tipo_de_vehiculo_desconocido(client):
    assert estimar(client, tipo_vehiculo="bicicleta").status_code == 422


def test_estimacion_sin_regla_activa_devuelve_422(client):
    regla = regla_activa(client, "auto")
    client.patch(f"{URL}/reglas/{regla['id']}", json={"activa": False})

    respuesta = estimar(client)

    assert respuesta.status_code == 422
    assert "auto" in respuesta.json()["detail"]


# --- Tarifa final -----------------------------------------------------------


def tarifa_final(client, viaje_id):
    return client.post(
        f"{URL}/viajes/{viaje_id}/tarifa-final",
        json={"tipo_vehiculo": "auto", "distancia_real_km": "10", "duracion_real_min": "20"},
    )


def test_tarifa_final_se_calcula_y_se_puede_consultar(client):
    viaje_id = str(uuid4())

    creada = tarifa_final(client, viaje_id)
    consultada = client.get(f"{URL}/viajes/{viaje_id}/tarifa-final")

    assert creada.status_code == 201
    assert creada.json()["viaje_id"] == viaje_id
    assert Decimal(creada.json()["desglose"]["total"]) == Decimal("6600")
    assert consultada.status_code == 200
    assert consultada.json() == creada.json()


def test_tarifa_final_no_se_calcula_dos_veces(client):
    viaje_id = str(uuid4())
    tarifa_final(client, viaje_id)

    assert tarifa_final(client, viaje_id).status_code == 409


def test_tarifa_final_inexistente_devuelve_404(client):
    assert client.get(f"{URL}/viajes/{uuid4()}/tarifa-final").status_code == 404


# --- Reglas -----------------------------------------------------------------


def test_reglas_iniciales_una_activa_por_tipo(client):
    reglas = client.get(f"{URL}/reglas").json()

    tipos = sorted(r["tipo_vehiculo"] for r in reglas if r["activa"])
    assert tipos == ["auto", "camioneta", "moto", "van"]


def test_listar_reglas_filtra_por_tipo(client):
    reglas = client.get(f"{URL}/reglas", params={"tipo_vehiculo": "moto"}).json()

    assert reglas and all(r["tipo_vehiculo"] == "moto" for r in reglas)


def test_crear_regla_activa_desactiva_la_anterior(client):
    anterior = regla_activa(client, "auto")
    nueva = {
        "tipo_vehiculo": "auto",
        "tarifa_base": "1000",
        "precio_por_km": "500",
        "precio_por_minuto": "70",
        "tarifa_minima": "2500",
    }

    respuesta = client.post(f"{URL}/reglas", json=nueva)

    assert respuesta.status_code == 201
    assert regla_activa(client, "auto")["id"] == respuesta.json()["id"]
    assert client.get(f"{URL}/reglas/{anterior['id']}").json()["activa"] is False


def test_crear_regla_inactiva_no_toca_la_vigente(client):
    vigente = regla_activa(client, "auto")
    nueva = {
        "tipo_vehiculo": "auto",
        "tarifa_base": "1",
        "precio_por_km": "1",
        "precio_por_minuto": "1",
        "tarifa_minima": "1",
        "activa": False,
    }

    client.post(f"{URL}/reglas", json=nueva)

    assert regla_activa(client, "auto")["id"] == vigente["id"]


def test_crear_regla_rechaza_precios_negativos(client):
    nueva = {
        "tipo_vehiculo": "auto",
        "tarifa_base": "-1",
        "precio_por_km": "1",
        "precio_por_minuto": "1",
        "tarifa_minima": "1",
    }

    assert client.post(f"{URL}/reglas", json=nueva).status_code == 422


def test_actualizar_regla_modifica_solo_lo_enviado(client):
    regla = regla_activa(client, "moto")

    respuesta = client.patch(f"{URL}/reglas/{regla['id']}", json={"precio_por_km": "300"})

    assert respuesta.status_code == 200
    assert Decimal(respuesta.json()["precio_por_km"]) == Decimal("300")
    assert respuesta.json()["tarifa_base"] == regla["tarifa_base"]


def test_reactivar_regla_desactiva_la_vigente(client):
    vieja = regla_activa(client, "auto")
    nueva = client.post(
        f"{URL}/reglas",
        json={
            "tipo_vehiculo": "auto",
            "tarifa_base": "1",
            "precio_por_km": "1",
            "precio_por_minuto": "1",
            "tarifa_minima": "1",
        },
    ).json()

    client.patch(f"{URL}/reglas/{vieja['id']}", json={"activa": True})

    assert regla_activa(client, "auto")["id"] == vieja["id"]
    assert client.get(f"{URL}/reglas/{nueva['id']}").json()["activa"] is False


def test_regla_inexistente_devuelve_404(client):
    assert client.get(f"{URL}/reglas/{uuid4()}").status_code == 404
    assert client.patch(f"{URL}/reglas/{uuid4()}", json={"activa": False}).status_code == 404
