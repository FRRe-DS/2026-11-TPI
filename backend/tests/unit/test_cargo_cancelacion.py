from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.errors import ErrorDominio
from app.schemas.cancelaciones import EstadoViaje, ReglaCargo
from app.services.cancelaciones import ReglasCancelacion, calcular_cargo

REGLAS = ReglasCancelacion(
    periodo_gracia=timedelta(minutes=5),
    cargo_asignado=Decimal("500"),
    cargo_conductor_en_punto=Decimal("1000"),
)
ASIGNADO = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def test_sin_cargo_antes_de_la_asignacion():
    assert calcular_cargo(EstadoViaje.solicitado, None, ASIGNADO, REGLAS) == (0, ReglaCargo.sin_asignar)


def test_sin_cargo_dentro_del_periodo_de_gracia():
    cancelado = ASIGNADO + timedelta(minutes=4, seconds=59)

    assert calcular_cargo(EstadoViaje.asignado, ASIGNADO, cancelado, REGLAS) == (0, ReglaCargo.dentro_periodo_gracia)


def test_el_limite_del_periodo_de_gracia_no_tiene_cargo():
    cancelado = ASIGNADO + timedelta(minutes=5)

    assert calcular_cargo(EstadoViaje.asignado, ASIGNADO, cancelado, REGLAS)[0] == 0


def test_cargo_fijo_pasado_el_periodo_de_gracia():
    cancelado = ASIGNADO + timedelta(minutes=6)

    assert calcular_cargo(EstadoViaje.asignado, ASIGNADO, cancelado, REGLAS) == (
        Decimal("500"),
        ReglaCargo.asignado_fuera_de_gracia,
    )


def test_cargo_mayor_si_el_conductor_ya_llego():
    assert calcular_cargo(EstadoViaje.conductor_en_punto, ASIGNADO, ASIGNADO, REGLAS) == (
        Decimal("1000"),
        ReglaCargo.conductor_en_punto,
    )


def test_viaje_asignado_sin_fecha_de_asignacion_es_422():
    with pytest.raises(ErrorDominio) as error:
        calcular_cargo(EstadoViaje.asignado, None, ASIGNADO, REGLAS)

    assert error.value.status_code == 422
    assert error.value.tipo == "/errores/falta-asignado-en"


@pytest.mark.parametrize("estado", [EstadoViaje.en_curso, EstadoViaje.finalizado, EstadoViaje.cancelado])
def test_no_se_cancela_un_viaje_en_curso_o_cerrado(estado):
    with pytest.raises(ErrorDominio) as error:
        calcular_cargo(estado, ASIGNADO, ASIGNADO, REGLAS)

    assert error.value.tipo == "/errores/viaje-no-cancelable"


def test_reglas_configurables(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cancelacion_periodo_gracia_min", 0)
    monkeypatch.setattr(settings, "cancelacion_cargo_asignado", Decimal("750"))
    reglas = ReglasCancelacion.desde_configuracion()

    assert calcular_cargo(EstadoViaje.asignado, ASIGNADO, ASIGNADO + timedelta(seconds=1), reglas)[0] == 750
