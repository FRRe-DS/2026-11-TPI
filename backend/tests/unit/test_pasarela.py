import time
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.pasarela import (
    TARJETA_RECHAZADA,
    TARJETA_SIN_RESPUESTA,
    TOKEN_RECHAZADO,
    TOKEN_SIN_RESPUESTA,
    PasarelaNoDisponible,
    PasarelaSimulada,
    con_timeout,
    obtener_pasarela,
)


@pytest.fixture
def pasarela():
    return PasarelaSimulada(demora_sin_respuesta_s=0.3)


def test_tokeniza_sin_devolver_el_numero(pasarela):
    token = pasarela.tokenizar("4111111111111111")

    assert token.startswith("tok_sim_")
    assert "4111" not in token


def test_tarjetas_de_prueba(pasarela):
    assert pasarela.tokenizar(TARJETA_RECHAZADA) == TOKEN_RECHAZADO
    assert pasarela.tokenizar(TARJETA_SIN_RESPUESTA) == TOKEN_SIN_RESPUESTA


def test_autoriza_y_captura(pasarela):
    autorizacion = pasarela.autorizar(uuid4(), Decimal("100"), "tok_sim_x")

    assert autorizacion.aprobado
    assert pasarela.capturar(autorizacion.referencia, Decimal("100")).aprobado
    assert pasarela.anular(autorizacion.referencia).aprobado
    assert pasarela.reembolsar(autorizacion.referencia, Decimal("10")).referencia.startswith(autorizacion.referencia)


def test_rechaza_el_token_de_prueba(pasarela):
    resultado = pasarela.autorizar(uuid4(), Decimal("100"), TOKEN_RECHAZADO)

    assert not resultado.aprobado
    assert resultado.motivo


def test_con_timeout_corta_la_espera(pasarela):
    inicio = time.perf_counter()

    with pytest.raises(PasarelaNoDisponible):
        con_timeout(pasarela.autorizar, uuid4(), Decimal("100"), TOKEN_SIN_RESPUESTA, timeout_s=0.05)

    assert time.perf_counter() - inicio < 0.25


def test_con_timeout_devuelve_el_resultado(pasarela):
    assert con_timeout(pasarela.autorizar, uuid4(), Decimal("1"), None, timeout_s=1).aprobado


def test_errores_de_conexion_se_informan_como_no_disponible():
    def falla():
        raise ConnectionError("sin red")

    with pytest.raises(PasarelaNoDisponible):
        con_timeout(falla, timeout_s=1)


def test_dependencia_por_defecto_es_la_simulada():
    assert isinstance(obtener_pasarela(), PasarelaSimulada)
