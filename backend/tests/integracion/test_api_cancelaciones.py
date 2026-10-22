from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.integraciones import ViajeExterno
from tests.integracion.conftest import autorizar, registrar_tarjeta

D = Decimal
URL = "/api/v1/cancelaciones"


def cancelar(client, actores, viaje_id, headers=None, **datos):
    cuerpo = {"viaje_id": str(viaje_id), "cliente_id": str(actores.cliente_id), "motivo": "Cambié de planes", **datos}
    return client.post(URL, json=cuerpo, headers=headers or actores.cliente)


def pago_autorizado(client, actores, viaje_id, con_tarjeta=True):
    metodo_id = registrar_tarjeta(client, actores)["id"] if con_tarjeta else None
    return autorizar(client, actores, metodo_id, viaje_id=viaje_id).json()


def test_sin_cargo_antes_de_la_asignacion_y_anula_la_autorizacion(client, actores):
    viaje_id = uuid4()
    pago = pago_autorizado(client, actores, viaje_id)

    respuesta = cancelar(client, actores, viaje_id, estado_viaje="solicitado")

    assert respuesta.status_code == 201, respuesta.text
    cargo = respuesta.json()
    assert (D(cargo["monto"]), cargo["regla_aplicada"]) == (0, "sin_asignar")
    assert cargo["pago_anulado_id"] == pago["id"]
    assert cargo["pago_cargo_id"] is None
    assert client.get(f"/api/v1/pagos/{pago['id']}", headers=actores.cliente).json()["estado"] == "anulado"


def test_sin_cargo_dentro_del_periodo_de_gracia(client, actores):
    viaje_id = uuid4()
    pago_autorizado(client, actores, viaje_id)
    asignado = datetime.now(timezone.utc) - timedelta(minutes=2)

    cargo = cancelar(client, actores, viaje_id, estado_viaje="asignado", asignado_en=asignado.isoformat()).json()

    assert (D(cargo["monto"]), cargo["regla_aplicada"]) == (0, "dentro_periodo_gracia")


def test_cargo_fijo_pasado_el_periodo_de_gracia_se_cobra_con_el_mismo_medio(client, actores, pasarela):
    viaje_id = uuid4()
    pago = pago_autorizado(client, actores, viaje_id)
    asignado = datetime.now(timezone.utc) - timedelta(minutes=10)

    cargo = cancelar(client, actores, viaje_id, estado_viaje="asignado", asignado_en=asignado.isoformat()).json()

    assert (D(cargo["monto"]), cargo["regla_aplicada"]) == (D("500"), "asignado_fuera_de_gracia")
    cobro = client.get(f"/api/v1/pagos/{cargo['pago_cargo_id']}", headers=actores.cliente).json()
    assert (cobro["tipo_operacion"], cobro["estado"]) == ("cargo_cancelacion", "capturado")
    assert (D(cobro["monto_capturado"]), cobro["metodo_pago_id"]) == (D("500"), pago["metodo_pago_id"])
    tipos = [
        m["tipo"]
        for m in client.get("/api/v1/movimientos", params={"viaje_id": str(viaje_id)}, headers=actores.cliente).json()
    ]
    assert tipos == ["autorizacion", "anulacion", "cargo_cancelacion", "autorizacion", "captura"]


def test_cargo_mayor_si_el_conductor_ya_llego(client, actores):
    viaje_id = uuid4()
    pago_autorizado(client, actores, viaje_id, con_tarjeta=False)

    cargo = cancelar(client, actores, viaje_id, estado_viaje="conductor_en_punto").json()

    assert (D(cargo["monto"]), cargo["regla_aplicada"]) == (D("1000"), "conductor_en_punto")
    cobro = client.get(f"/api/v1/pagos/{cargo['pago_cargo_id']}", headers=actores.cliente).json()
    assert (cobro["metodo"], cobro["estado"]) == ("efectivo", "capturado")


def test_cargo_sin_cobro_previo_queda_registrado_sin_pago(client, actores):
    cargo = cancelar(client, actores, uuid4(), estado_viaje="conductor_en_punto").json()

    assert D(cargo["monto"]) == D("1000")
    assert cargo["pago_cargo_id"] is None and cargo["pago_anulado_id"] is None


def test_una_sola_cancelacion_por_viaje(client, actores):
    viaje_id = uuid4()
    cancelar(client, actores, viaje_id, estado_viaje="solicitado")

    respuesta = cancelar(client, actores, viaje_id, estado_viaje="solicitado")

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "/errores/cancelacion-duplicada"


def test_viaje_en_curso_no_se_cancela(client, actores):
    respuesta = cancelar(client, actores, uuid4(), estado_viaje="en_curso")

    assert respuesta.json()["type"] == "/errores/viaje-no-cancelable"


def test_el_estado_se_consulta_a_m6(client, actores, m6, integraciones):
    integraciones["m6"] = True
    viaje_id = uuid4()
    m6.viajes[viaje_id] = ViajeExterno(viaje_id, "asignado", datetime.now(timezone.utc) - timedelta(minutes=30))

    cargo = cancelar(client, actores, viaje_id).json()

    assert (cargo["estado_viaje"], D(cargo["monto"])) == ("asignado", D("500"))


def test_estado_desconocido_en_m6(client, actores, m6, integraciones):
    integraciones["m6"] = True
    viaje_id = uuid4()
    m6.viajes[viaje_id] = ViajeExterno(viaje_id, "volando")

    assert cancelar(client, actores, viaje_id).json()["type"] == "/errores/estado-viaje-desconocido"


def test_sin_m6_hay_que_enviar_el_estado(client, actores):
    respuesta = cancelar(client, actores, uuid4())

    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/estado-viaje-desconocido"


def test_el_cobro_del_viaje_debe_ser_del_mismo_cliente(client, actores):
    viaje_id = uuid4()
    pago_autorizado(client, actores, viaje_id)

    respuesta = cancelar(
        client, actores, viaje_id, headers=actores.servicio, cliente_id=str(uuid4()), estado_viaje="solicitado"
    )

    assert respuesta.json()["type"] == "/errores/cliente-no-coincide"


def test_consultar_cancelacion(client, actores):
    viaje_id = uuid4()
    creada = cancelar(client, actores, viaje_id, estado_viaje="solicitado").json()

    assert client.get(f"{URL}/{viaje_id}", headers=actores.cliente).json() == creada
    assert client.get(f"{URL}/{viaje_id}", headers=actores.headers("cliente")).status_code == 403
    assert client.get(f"{URL}/{uuid4()}", headers=actores.operador).status_code == 404


def test_un_cliente_no_cancela_viajes_ajenos(client, actores):
    respuesta = cancelar(client, actores, uuid4(), cliente_id=str(uuid4()), estado_viaje="solicitado")

    assert respuesta.status_code == 403
