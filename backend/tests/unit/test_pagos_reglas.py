from decimal import Decimal

import pytest

from app.core.errors import ErrorDominio
from app.schemas.pagos import EstadoPago
from app.services.pagos import TRANSICIONES, calcular_reembolso, monto_a_capturar, validar_transicion

D = Decimal
E = EstadoPago


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        (E.pendiente_confirmacion, E.autorizado),
        (E.pendiente_confirmacion, E.rechazado),
        (E.autorizado, E.capturado),
        (E.autorizado, E.captura_pendiente),
        (E.autorizado, E.anulado),
        (E.captura_pendiente, E.capturado),
        (E.captura_pendiente, E.rechazado),
        (E.capturado, E.reembolsado_parcial),
        (E.capturado, E.reembolsado),
        (E.reembolsado_parcial, E.reembolsado_parcial),
        (E.reembolsado_parcial, E.reembolsado),
    ],
)
def test_transiciones_validas(actual, nuevo):
    validar_transicion(actual, nuevo)


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        (E.pendiente_confirmacion, E.capturado),
        (E.autorizado, E.reembolsado),
        (E.capturado, E.capturado),
        (E.capturado, E.anulado),
        (E.captura_pendiente, E.anulado),
        (E.rechazado, E.autorizado),
        (E.anulado, E.capturado),
        (E.reembolsado, E.reembolsado_parcial),
    ],
)
def test_transiciones_invalidas(actual, nuevo):
    with pytest.raises(ErrorDominio) as error:
        validar_transicion(actual, nuevo)

    assert error.value.status_code == 409
    assert error.value.tipo == "/errores/transicion-invalida"


def test_todos_los_estados_tienen_transiciones_definidas():
    assert set(TRANSICIONES) == set(EstadoPago)


@pytest.mark.parametrize("final", [E.rechazado, E.anulado, E.reembolsado])
def test_estados_finales(final):
    assert TRANSICIONES[final] == set()


# --- Reembolsos -------------------------------------------------------------


def test_reembolso_parcial():
    assert calcular_reembolso(D("1000"), D("0"), D("300")) == (D("300"), E.reembolsado_parcial)


def test_reembolso_total_sin_monto():
    assert calcular_reembolso(D("1000"), D("0"), None) == (D("1000"), E.reembolsado)


def test_reembolso_del_saldo_restante():
    assert calcular_reembolso(D("1000"), D("300"), None) == (D("700"), E.reembolsado)


def test_reembolsos_parciales_que_completan_el_total():
    assert calcular_reembolso(D("1000"), D("600"), D("400")) == (D("400"), E.reembolsado)


def test_reembolso_que_excede_lo_reembolsable():
    with pytest.raises(ErrorDominio) as error:
        calcular_reembolso(D("1000"), D("800"), D("201"))

    assert error.value.status_code == 422
    assert error.value.tipo == "/errores/monto-excede-reembolsable"


# --- Captura ----------------------------------------------------------------


def test_captura_usa_el_monto_pedido():
    assert monto_a_capturar(D("5000"), D("4200"), D("4000")) == D("4200")


def test_captura_usa_la_tarifa_final_si_no_hay_monto():
    assert monto_a_capturar(D("5000"), None, D("4000")) == D("4000")


def test_captura_usa_lo_autorizado_sin_tarifa_final():
    assert monto_a_capturar(D("5000"), None, None) == D("5000")


def test_captura_no_supera_lo_autorizado():
    with pytest.raises(ErrorDominio) as error:
        monto_a_capturar(D("5000"), None, D("5000.01"))

    assert error.value.tipo == "/errores/monto-excede-autorizado"
