from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.errors import ErrorDominio
from app.schemas.liquidaciones import EstadoLiquidacion
from app.services.liquidaciones import calcular_montos, calcular_saldo, neto_pago, validar_transicion

D = Decimal
L = EstadoLiquidacion


def test_comision_del_20_por_ciento():
    montos = calcular_montos([D("1000"), D("500")], D("0.20"))

    assert (montos.bruto, montos.comision, montos.neto) == (D("1500"), D("300.00"), D("1200.00"))


def test_comision_configurable():
    assert calcular_montos([D("1000")], D("0.15")).neto == D("850.00")


def test_comision_redondea_a_centavos():
    # 333.33 * 0.2 = 66.666 -> 66.67
    montos = calcular_montos([D("333.33")], D("0.20"))

    assert montos.comision == D("66.67")
    assert montos.neto == D("266.66")


def test_sin_comision():
    assert calcular_montos([D("100")], D("0")).neto == D("100")


def test_neto_descuenta_lo_reembolsado():
    assert neto_pago(D("1000"), D("400")) == D("600")


def test_saldo_separa_pendiente_liquidado_y_transferido():
    saldo = calcular_saldo(
        uuid4(),
        [D("200"), D("50")],
        [(L.pendiente, D("400")), (L.transferida, D("800")), (L.transferida, D("100")), (L.anulada, D("999"))],
    )

    assert saldo.saldo_pendiente_liquidar == D("250")
    assert saldo.liquidado_pendiente_transferir == D("400")
    assert saldo.total_transferido == D("900")


def test_saldo_sin_movimientos_es_cero():
    saldo = calcular_saldo(uuid4(), [], [])

    assert saldo.saldo_pendiente_liquidar == saldo.total_transferido == 0


@pytest.mark.parametrize("nuevo", [L.transferida, L.anulada])
def test_una_liquidacion_pendiente_se_transfiere_o_anula(nuevo):
    validar_transicion(L.pendiente, nuevo)


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [(L.transferida, L.anulada), (L.transferida, L.transferida), (L.anulada, L.transferida), (L.pendiente, L.pendiente)],
)
def test_transiciones_invalidas_de_liquidacion(actual, nuevo):
    with pytest.raises(ErrorDominio) as error:
        validar_transicion(actual, nuevo)

    assert error.value.status_code == 409
