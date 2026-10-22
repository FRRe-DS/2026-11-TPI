"""El contrato escrito a mano (contratos/m7_tarifas/openapi.yml) debe coincidir con lo implementado."""

import re
from pathlib import Path

import pytest
import yaml

from app.main import app
from app.schemas.cancelaciones import EstadoViaje, ReglaCargo
from app.schemas.liquidaciones import EstadoLiquidacion
from app.schemas.movimientos import TipoMovimiento
from app.schemas.pagos import EstadoPago, TipoMetodoPago, TipoOperacion
from app.schemas.tarifas import TipoVehiculo

CONTRATO = Path(__file__).resolve().parents[3] / "contratos" / "m7_tarifas" / "openapi.yml"
METODOS = {"get", "post", "put", "patch", "delete"}

# Nombre del modelo en la implementación -> nombre del esquema en el contrato
ESQUEMAS = {
    "ReglaTarifaCreate": "ReglaTarifaNueva",
    "ReglaTarifaUpdate": "ReglaTarifaCambios",
    "ReglaTarifa": "ReglaTarifa",
    "Coordenada": "Coordenada",
    "EstimacionRequest": "EstimacionSolicitud",
    "DesgloseTarifa": "Desglose",
    "Estimacion": "Estimacion",
    "TarifaFinalRequest": "TarifaFinalSolicitud",
    "TarifaFinal": "TarifaFinal",
    "MetodoPagoCreate": "MetodoPagoNuevo",
    "MetodoPago": "MetodoPago",
    "PagoCreate": "PagoNuevo",
    "Pago": "Pago",
    "CapturaRequest": "Captura",
    "ReembolsoCreate": "ReembolsoNuevo",
    "Reembolso": "Reembolso",
    "WebhookPasarela": "WebhookPasarela",
    "CancelacionCreate": "CancelacionNueva",
    "CargoCancelacion": "CargoCancelacion",
    "MovimientoFinanciero": "MovimientoFinanciero",
    "LiquidacionCreate": "LiquidacionNueva",
    "Liquidacion": "Liquidacion",
    "TransferenciaConfirmacion": "Transferencia",
    "Saldo": "Saldo",
}

ENUMS = {
    "TipoVehiculo": TipoVehiculo,
    "TipoMetodoPago": TipoMetodoPago,
    "TipoOperacion": TipoOperacion,
    "EstadoPago": EstadoPago,
    "EstadoLiquidacion": EstadoLiquidacion,
    "EstadoViaje": EstadoViaje,
    "ReglaCargo": ReglaCargo,
    "TipoMovimiento": TipoMovimiento,
}


@pytest.fixture(scope="module")
def contrato() -> dict:
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def implementado() -> dict:
    return app.openapi()


def _operaciones(spec: dict) -> dict[tuple[str, str], dict]:
    """(ruta con parámetros normalizados, método) -> operación."""
    return {
        (re.sub(r"\{[^}]+\}", "{}", ruta), metodo): operacion
        for ruta, item in spec["paths"].items()
        for metodo, operacion in item.items()
        if metodo in METODOS
    }


def test_es_openapi_3_1(contrato):
    assert contrato["openapi"] == "3.1.0"


def test_mismas_rutas_y_metodos(contrato, implementado):
    assert set(_operaciones(contrato)) == set(_operaciones(implementado))


def test_mismos_nombres_de_parametros_de_ruta(contrato, implementado):
    assert set(contrato["paths"]) == set(implementado["paths"])


def test_codigos_de_exito_documentados(contrato, implementado):
    del_contrato = _operaciones(contrato)
    for clave, operacion in _operaciones(implementado).items():
        exito = {c for c in operacion["responses"] if c.startswith("2")}
        assert exito <= set(del_contrato[clave]["responses"]), clave


def test_toda_operacion_documenta_sus_errores(contrato):
    for (ruta, metodo), operacion in _operaciones(contrato).items():
        codigos = set(operacion["responses"])
        assert "500" in codigos, (ruta, metodo)
        if operacion.get("security") != []:
            assert {"401", "403"} <= codigos, (ruta, metodo)


@pytest.mark.parametrize(("modelo", "esquema"), ESQUEMAS.items())
def test_mismas_propiedades_en_cada_esquema(contrato, implementado, modelo, esquema):
    componentes = implementado["components"]["schemas"]
    nombre = next(n for n in (modelo, f"{modelo}-Output", f"{modelo}-Input") if n in componentes)

    assert set(contrato["components"]["schemas"][esquema]["properties"]) == set(componentes[nombre]["properties"])


@pytest.mark.parametrize(("nombre", "enum"), ENUMS.items())
def test_mismos_valores_en_los_enums(contrato, nombre, enum):
    assert contrato["components"]["schemas"][nombre]["enum"] == [e.value for e in enum]


def test_todas_las_referencias_existen(contrato):
    referencias = set(re.findall(r"\$ref: '#/([^']+)'", CONTRATO.read_text(encoding="utf-8")))

    for referencia in referencias:
        nodo = contrato
        for parte in referencia.split("/"):
            assert parte in nodo, referencia
            nodo = nodo[parte]


def test_scopes_declarados_existen(contrato):
    declarados = set(contrato["components"]["securitySchemes"]["keycloak"]["flows"]["clientCredentials"]["scopes"])
    for operacion in _operaciones(contrato).values():
        for requisito in operacion.get("security", []):
            assert set(requisito.get("keycloak", [])) <= declarados
