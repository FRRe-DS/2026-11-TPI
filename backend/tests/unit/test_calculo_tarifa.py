from decimal import Decimal
from uuid import uuid4

import pytest

from app.schemas.tarifas import ReglaTarifa, TipoVehiculo
from app.services.tarifas import calcular_desglose, redondear

D = Decimal


def regla(base="900", km="450", minuto="60", minima="2000") -> ReglaTarifa:
    return ReglaTarifa(
        id=uuid4(),
        tipo_vehiculo=TipoVehiculo.auto,
        tarifa_base=D(base),
        precio_por_km=D(km),
        precio_por_minuto=D(minuto),
        tarifa_minima=D(minima),
    )


def test_suma_base_distancia_y_tiempo():
    desglose = calcular_desglose(regla(), D("10"), D("20"), D("1"))

    assert desglose.tarifa_base == D("900.00")
    assert desglose.cargo_distancia == D("4500.00")
    assert desglose.cargo_tiempo == D("1200.00")
    assert desglose.total == D("6600.00")


def test_aplica_el_multiplicador_de_demanda_al_subtotal():
    assert calcular_desglose(regla(), D("10"), D("20"), D("1.5")).total == D("9900.00")


def test_respeta_la_tarifa_minima():
    # 900 + 450 + 60 = 1410, por debajo de la mínima de 2000
    assert calcular_desglose(regla(), D("1"), D("1"), D("1")).total == D("2000.00")


def test_la_minima_se_compara_despues_del_multiplicador():
    # (900 + 450 + 60) * 1.5 = 2115, ya supera la mínima
    assert calcular_desglose(regla(), D("1"), D("1"), D("1.5")).total == D("2115.00")


def test_redondea_a_centavos_con_mitad_hacia_arriba():
    # 900 + 450 * 10.333 + 1200 = 6749.85
    assert calcular_desglose(regla(), D("10.333"), D("20"), D("1")).total == D("6749.85")


@pytest.mark.parametrize(("valor", "esperado"), [("1.005", "1.01"), ("1.004", "1.00"), ("2.675", "2.68")])
def test_redondear(valor, esperado):
    assert redondear(D(valor)) == D(esperado)


def test_no_usa_float():
    desglose = calcular_desglose(regla(), D("0.1"), D("0.2"), D("1.1"))

    assert all(isinstance(v, Decimal) for v in desglose.model_dump().values())
