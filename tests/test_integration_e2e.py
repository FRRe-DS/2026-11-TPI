import uuid
from sqlalchemy import select
from app.models import Liquidacion, MedioPago, Pago


def test_flujo_completo_e2e(client, db_session):
    print("\n" + "=" * 70)
    print("🚀 INICIANDO TEST END-TO-END CON SQLALCHEMY ORM")
    print("=" * 70)

    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    print(f"\n[1/12] GET /health -> {res_health.json()}")

    # 2. Obtener parámetros de tarifas desde la base de datos
    res_param = client.get("/tarifas/parametros")
    assert res_param.status_code == 200
    params = res_param.json()
    assert len(params) >= 2
    vehiculos = {p["tipo_vehiculo"] for p in params}
    assert "auto" in vehiculos
    assert "moto" in vehiculos
    print(f"[2/12] GET /tarifas/parametros -> {len(params)} vehículos configurados: { sorted(vehiculos) }")

    # 3. Estimar tarifa para auto (10 km, 20 min)
    res_estimar = client.post(
        "/tarifas/estimar",
        json={"tipo_vehiculo": "auto", "distancia_km": 10.0, "tiempo_min": 20.0},
    )
    assert res_estimar.status_code == 200
    data_estimar = res_estimar.json()
    assert data_estimar["tipo_vehiculo"] == "auto"
    assert data_estimar["total"] == 3000.0  # 500 + (150*10) + (50*20) = 3000
    print(f"[3/12] POST /tarifas/estimar -> Total estimado: ${data_estimar['total']} {data_estimar['moneda']}")

    # 4. Registrar medio de pago para cliente
    cliente_id = str(uuid.uuid4())
    res_medio = client.post(
        "/pagos/medios",
        json={
            "cliente_id": cliente_id,
            "tipo": "tarjeta",
            "alias": "Visa Platinum",
            "ultimos4": "4321",
            "predeterminado": True,
        },
    )
    assert res_medio.status_code == 200
    medio_data = res_medio.json()
    medio_id = medio_data["id"]
    assert medio_data["alias"] == "Visa Platinum"
    print(f"[4/12] POST /pagos/medios -> Creado MedioPago ORM id={medio_id} ({medio_data['alias']})")

    # 5. Listar medios de pago del cliente
    res_lista_medios = client.get(f"/pagos/medios/{cliente_id}")
    assert res_lista_medios.status_code == 200
    lista = res_lista_medios.json()
    assert len(lista) == 1
    assert lista[0]["id"] == medio_id
    print(f"[5/12] GET /pagos/medios/{cliente_id} -> {len(lista)} medio(s) encontrado(s)")

    # 6. Autorizar pago de viaje con idempotencia
    viaje_id = f"viaje-{uuid.uuid4()}"
    conductor_id = str(uuid.uuid4())
    idempotency_autorizar = f"idemp-auth-{uuid.uuid4()}"

    payload_auth = {
        "viaje_id": viaje_id,
        "cliente_id": cliente_id,
        "conductor_id": conductor_id,
        "medio_pago_id": medio_id,
        "tipo_vehiculo": "auto",
        "monto_estimado": 3000.0,
        "comision_pct": 15.0,
        "idempotency_key": idempotency_autorizar,
    }
    res_auth = client.post("/pagos/autorizar", json=payload_auth)
    assert res_auth.status_code == 200
    data_auth = res_auth.json()
    assert data_auth["mensaje"] == "Pago autorizado"
    pago_id = data_auth["pago"]["id"]
    assert data_auth["pago"]["estado"] == "autorizado"
    print(f"[6/12] POST /pagos/autorizar -> Pago id={pago_id}, estado='{data_auth['pago']['estado']}'")

    # 6b. Probar idempotencia de autorización (mismo idempotency_key)
    res_auth_repetido = client.post("/pagos/autorizar", json=payload_auth)
    assert res_auth_repetido.status_code == 200
    assert res_auth_repetido.json()["mensaje"] == "Operación ya procesada"
    assert res_auth_repetido.json()["pago"]["id"] == pago_id
    print(f"[6b/12] POST /pagos/autorizar (repetido) -> '{res_auth_repetido.json()['mensaje']}' (idempotencia OK)")

    # 7. Capturar pago al finalizar el viaje
    idempotency_captura = f"idemp-cap-{uuid.uuid4()}"
    res_cap = client.post(
        "/pagos/capturar",
        json={
            "pago_id": pago_id,
            "monto_final": 3200.0,
            "idempotency_key": idempotency_captura,
        },
    )
    assert res_cap.status_code == 200
    data_cap = res_cap.json()
    assert data_cap["mensaje"] == "Pago capturado"
    assert data_cap["pago"]["estado"] == "capturado"
    assert float(data_cap["pago"]["monto_final"]) == 3200.0
    print(f"[7/12] POST /pagos/capturar -> estado='{data_cap['pago']['estado']}', monto_final=${data_cap['pago']['monto_final']}")

    # 8. Consultar pago por viaje_id
    res_pago = client.get(f"/pagos/{viaje_id}")
    assert res_pago.status_code == 200
    assert res_pago.json()["id"] == pago_id
    print(f"[8/12] GET /pagos/{viaje_id} -> Pago recuperado correctamente")

    # 9. Consultar historial financiero del viaje
    res_historial = client.get(f"/pagos/{viaje_id}/historial")
    assert res_historial.status_code == 200
    historial = res_historial.json()
    assert len(historial) >= 2  # autorizacion y captura
    tipos_operaciones = [op["tipo"] for op in historial]
    assert "captura" in tipos_operaciones
    assert "autorizacion" in tipos_operaciones
    print(f"[9/12] GET /pagos/{viaje_id}/historial -> Operaciones registradas: {tipos_operaciones}")

    # 10. Reintegro parcial
    idempotency_reintegro = f"idemp-reint-{uuid.uuid4()}"
    res_reintegro = client.post(
        "/pagos/reintegrar",
        json={
            "pago_id": pago_id,
            "monto": 500.0,
            "motivo": "Descuento promocional posterior",
            "idempotency_key": idempotency_reintegro,
        },
    )
    assert res_reintegro.status_code == 200
    assert res_reintegro.json()["pago"]["estado"] == "reintegrado_parcial"
    print(f"[10/12] POST /pagos/reintegrar -> Nuevo estado='{res_reintegro.json()['pago']['estado']}'")

    # 11. Crear liquidación para el conductor con idempotencia
    idempotency_liq = f"idemp-liq-{uuid.uuid4()}"
    payload_liq = {
        "conductor_id": conductor_id,
        "desde": "2026-10-01 00:00:00",
        "hasta": "2026-10-15 23:59:59",
        "cantidad_viajes": 1,
        "bruto": 3200.0,
        "comision": 480.0,
        "neto": 2720.0,
        "idempotency_key": idempotency_liq,
    }
    res_liq = client.post("/liquidaciones", json=payload_liq)
    assert res_liq.status_code == 200
    data_liq = res_liq.json()
    assert data_liq["mensaje"] == "Liquidación creada"
    assert data_liq["liquidacion"]["conductor_id"] == conductor_id
    print(f"[11/12] POST /liquidaciones -> Liquidación id={data_liq['liquidacion']['id']}, neto=${data_liq['liquidacion']['neto']}")

    # 12. Listar liquidaciones del conductor
    res_liq_list = client.get(f"/liquidaciones/{conductor_id}")
    assert res_liq_list.status_code == 200
    liq_items = res_liq_list.json()
    assert len(liq_items) >= 1
    assert liq_items[0]["conductor_id"] == conductor_id
    print(f"[12/12] GET /liquidaciones/{conductor_id} -> {len(liq_items)} liquidación(es) encontrada(s)")

    # Verificación directa de objetos y relaciones ORM en la sesión SQLAlchemy
    pago_orm = db_session.scalar(select(Pago).where(Pago.id == pago_id))
    medio_orm = db_session.scalar(select(MedioPago).where(MedioPago.id == medio_id))
    liq_orm = db_session.scalar(select(Liquidacion).where(Liquidacion.conductor_id == conductor_id))

    assert pago_orm is not None
    assert len(pago_orm.operaciones) == 3  # autorizacion, captura, reintegro
    print("\n" + "-" * 70)
    print("🔎 INSPECCIÓN DE OBJETOS ORM EN LA SESIÓN DE SQLALCHEMY:")
    print(f"   • Instancia Pago:       {pago_orm!r} (estado={pago_orm.estado})")
    print(f"   • Relación pago.operaciones ({len(pago_orm.operaciones)} items): {[op.tipo for op in pago_orm.operaciones]}")
    print(f"   • Instancia MedioPago:  {medio_orm!r} (alias={medio_orm.alias})")
    print(f"   • Instancia Liquidacion:{liq_orm!r} (neto={liq_orm.neto})")
    print("=" * 70)
