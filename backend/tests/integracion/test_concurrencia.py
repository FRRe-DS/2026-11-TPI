"""Solicitudes en paralelo contra la base real (RNF-08): nunca dos cobros, capturas o reembolsos."""

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from app.core.errors import ErrorDominio
from app.core.security import Usuario
from app.db.session import SessionLocal
from app.schemas.pagos import CapturaRequest, PagoCreate, ReembolsoCreate
from app.services import pagos
from tests.integracion.conftest import ejecutar_sql, pago_capturado

HILOS = 8
SERVICIO = Usuario(sub="m6", roles=frozenset({"servicio"}), scopes=frozenset({"*"}))


def en_paralelo(funcion, veces=HILOS):
    """Arranca todas las llamadas a la vez (barrera) y devuelve resultado o excepción de cada una."""
    barrera = threading.Barrier(veces)

    def ejecutar(_):
        with SessionLocal() as db:
            barrera.wait()
            try:
                return funcion(db)
            except ErrorDominio as exc:
                return exc

    with ThreadPoolExecutor(max_workers=veces) as ejecutor:
        return list(ejecutor.map(ejecutar, range(veces)))


def datos_pago(viaje_id) -> PagoCreate:
    return PagoCreate(viaje_id=viaje_id, cliente_id=uuid4(), beneficiario_id=uuid4(), monto=Decimal("1000"))


def test_cobros_simultaneos_del_mismo_viaje_dejan_uno_solo(pasarela):
    viaje_id = uuid4()

    resultados = en_paralelo(lambda db: pagos.autorizar(db, datos_pago(viaje_id), None, SERVICIO, pasarela))

    creados = [r for r in resultados if not isinstance(r, Exception)]
    conflictos = [r for r in resultados if isinstance(r, ErrorDominio)]
    assert len(creados) == 1
    assert len(conflictos) == HILOS - 1
    assert {c.status_code for c in conflictos} == {409}
    assert ejecutar_sql("SELECT count(*) FROM pagos WHERE viaje_id = :v", v=viaje_id).scalar() == 1


def test_misma_idempotency_key_en_paralelo_crea_un_solo_pago(pasarela):
    datos = datos_pago(uuid4())

    resultados = en_paralelo(lambda db: pagos.autorizar(db, datos, "clave-unica", SERVICIO, pasarela))

    assert not [r for r in resultados if isinstance(r, Exception)]
    assert len({pago.id for pago, _ in resultados}) == 1
    assert sum(creado for _, creado in resultados) == 1
    assert ejecutar_sql("SELECT count(*) FROM pagos").scalar() == 1


def test_capturas_simultaneas_cobran_una_vez(client, actores, pasarela):
    pago = client.post(
        "/api/v1/pagos",
        json={
            "viaje_id": str(uuid4()),
            "cliente_id": str(actores.cliente_id),
            "beneficiario_id": str(actores.conductor_id),
            "monto": "1000",
        },
        headers=actores.servicio,
    ).json()

    resultados = en_paralelo(lambda db: pagos.capturar(db, pago["id"], CapturaRequest(), SERVICIO, pasarela))

    assert len([r for r in resultados if not isinstance(r, Exception)]) == 1
    capturas = ejecutar_sql(
        "SELECT count(*) FROM movimientos_financieros WHERE pago_id = :p AND tipo = 'captura'", p=pago["id"]
    ).scalar()
    assert capturas == 1


def test_reembolsos_simultaneos_no_superan_lo_cobrado(client, actores, pasarela):
    pago = pago_capturado(client, actores, monto="1000", con_tarjeta=True)

    resultados = en_paralelo(
        lambda db: pagos.reembolsar(db, pago["id"], ReembolsoCreate(monto=Decimal("400"), motivo="x"), None, SERVICIO,
                                    pasarela)
    )

    exitosos = [r for r in resultados if not isinstance(r, Exception)]
    assert len(exitosos) == 2  # 400 + 400; el tercero excedería los 1000
    total = ejecutar_sql("SELECT monto_reembolsado FROM pagos WHERE id = :p", p=pago["id"]).scalar()
    assert total == Decimal("800")


def test_liquidaciones_simultaneas_no_comparten_pagos(client, actores):
    from datetime import datetime, timezone

    from app.schemas.liquidaciones import LiquidacionCreate
    from app.services import liquidaciones

    for _ in range(3):
        pago_capturado(client, actores)
    hoy = datetime.now(timezone.utc).date()
    datos = LiquidacionCreate(beneficiario_id=actores.conductor_id, periodo_desde=hoy, periodo_hasta=hoy)

    resultados = en_paralelo(lambda db: liquidaciones.generar_liquidacion(db, datos, SERVICIO), veces=4)

    generadas = [r for r in resultados if not isinstance(r, Exception)]
    assert len(generadas) == 1
    assert len(generadas[0].pago_ids) == 3
