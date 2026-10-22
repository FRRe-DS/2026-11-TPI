"""Recorrido feliz: estimar, autorizar, capturar, liquidar y transferir."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from tests.integracion.conftest import registrar_tarjeta

D = Decimal


def test_flujo_completo_con_tarjeta(client, actores, pasarela):
    hoy = datetime.now(timezone.utc).date().isoformat()
    viaje_id = str(uuid4())

    # 1. El cliente registra su tarjeta
    metodo = registrar_tarjeta(client, actores)

    # 2. M5 pide una estimación y la referencia por id
    estimacion = client.post(
        "/api/v1/tarifas/estimaciones",
        json={"tipo_vehiculo": "auto", "distancia_km": "10", "duracion_estimada_min": "20"},
        headers=actores.servicio,
    )
    assert estimacion.status_code == 201
    assert D(estimacion.json()["desglose"]["total"]) == D("6600")
    assert estimacion.headers["Location"].endswith(estimacion.json()["id"])

    # 3. Al asignarse el viaje se autoriza el total estimado
    autorizacion = client.post(
        "/api/v1/pagos",
        json={
            "viaje_id": viaje_id,
            "cliente_id": str(actores.cliente_id),
            "beneficiario_id": str(actores.conductor_id),
            "metodo_pago_id": metodo["id"],
            "estimacion_id": estimacion.json()["id"],
        },
        headers={**actores.servicio, "Idempotency-Key": "viaje-1-autorizacion"},
    )
    assert autorizacion.status_code == 201, autorizacion.text
    pago = autorizacion.json()
    assert pago["estado"] == "autorizado"
    assert D(pago["monto"]) == D("6600")
    assert pago["metodo"] == "tarjeta"

    # 4. M6 informa el final del viaje: se calcula la tarifa final
    final = client.post(
        f"/api/v1/tarifas/viajes/{viaje_id}/tarifa-final",
        json={"tipo_vehiculo": "auto", "distancia_real_km": "9", "duracion_real_min": "18"},
        headers=actores.servicio,
    )
    assert D(final.json()["desglose"]["total"]) == D("6030")

    # 5. Se captura sin indicar monto: se usa la tarifa final
    captura = client.post(f"/api/v1/pagos/{pago['id']}/captura", headers=actores.servicio)
    assert captura.status_code == 200, captura.text
    assert captura.json()["estado"] == "capturado"
    assert D(captura.json()["monto_capturado"]) == D("6030")

    # 6. El operador liquida al conductor
    liquidacion = client.post(
        "/api/v1/liquidaciones",
        json={"beneficiario_id": str(actores.conductor_id), "periodo_desde": hoy, "periodo_hasta": hoy},
        headers=actores.operador,
    )
    assert liquidacion.status_code == 201, liquidacion.text
    liq = liquidacion.json()
    assert (D(liq["monto_bruto"]), D(liq["comision_plataforma"]), D(liq["monto_neto"])) == (
        D("6030"),
        D("1206"),
        D("4824"),
    )
    assert liq["pago_ids"] == [pago["id"]]

    saldo = client.get(f"/api/v1/liquidaciones/saldos/{actores.conductor_id}", headers=actores.conductor).json()
    assert D(saldo["liquidado_pendiente_transferir"]) == D("4824")

    # 7. El operador confirma la transferencia
    transferencia = client.post(
        f"/api/v1/liquidaciones/{liq['id']}/transferencia",
        json={"referencia_transferencia": "CBU-0001"},
        headers=actores.operador,
    )
    assert transferencia.json()["estado"] == "transferida"
    saldo = client.get(f"/api/v1/liquidaciones/saldos/{actores.conductor_id}", headers=actores.conductor).json()
    assert D(saldo["total_transferido"]) == D("4824")
    assert D(saldo["liquidado_pendiente_transferir"]) == 0

    # 8. El historial financiero refleja cada paso
    del_cliente = client.get("/api/v1/movimientos", params={"viaje_id": viaje_id}, headers=actores.cliente).json()
    assert [m["tipo"] for m in del_cliente] == ["autorizacion", "captura"]
    de_la_liquidacion = client.get(
        "/api/v1/movimientos", params={"liquidacion_id": liq["id"]}, headers=actores.operador
    ).json()
    assert [m["tipo"] for m in de_la_liquidacion] == ["liquidacion_generada", "liquidacion_transferida"]
    assert pasarela.llamadas == ["autorizar", "capturar"]


def test_flujo_en_efectivo_no_usa_la_pasarela(client, actores, pasarela):
    pago = client.post(
        "/api/v1/pagos",
        json={
            "viaje_id": str(uuid4()),
            "cliente_id": str(actores.cliente_id),
            "beneficiario_id": str(actores.conductor_id),
            "monto": "3000",
        },
        headers=actores.cliente,
    ).json()
    assert (pago["metodo"], pago["estado"]) == ("efectivo", "autorizado")

    captura = client.post(f"/api/v1/pagos/{pago['id']}/captura", json={"monto": "2800"}, headers=actores.servicio)

    assert captura.json()["estado"] == "capturado"
    assert D(captura.json()["monto_capturado"]) == D("2800")
    assert pasarela.llamadas == []
