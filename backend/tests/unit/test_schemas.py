from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.cancelaciones import CancelacionCreate
from app.schemas.liquidaciones import LiquidacionCreate
from app.schemas.metodos_pago import MetodoPagoCreate, luhn_valido
from app.schemas.pagos import CapturaRequest, PagoCreate, ReembolsoCreate, WebhookPasarela
from app.schemas.tarifas import EstimacionRequest, ReglaTarifaCreate
from app.services.metodos_pago import marca_tarjeta

VISA = "4111111111111111"


def pago(**cambios) -> dict:
    return {
        "viaje_id": str(uuid4()),
        "cliente_id": str(uuid4()),
        "beneficiario_id": str(uuid4()),
        "monto": "1000",
        **cambios,
    }


# --- Tarifas ----------------------------------------------------------------


def test_estimacion_con_distancia_y_duracion():
    EstimacionRequest(tipo_vehiculo="auto", distancia_km="10", duracion_estimada_min="20")


def test_estimacion_con_origen_y_destino():
    EstimacionRequest(tipo_vehiculo="moto", origen={"lat": -27.45, "lng": -58.98}, destino={"lat": -27.47, "lng": -58.83})


@pytest.mark.parametrize(
    "datos",
    [
        {"tipo_vehiculo": "auto"},
        {"tipo_vehiculo": "auto", "distancia_km": "10"},
        {"tipo_vehiculo": "auto", "origen": {"lat": 0, "lng": 0}},
        {"tipo_vehiculo": "camioneta", "distancia_km": "1", "duracion_estimada_min": "1"},
        {"tipo_vehiculo": "auto", "distancia_km": "0", "duracion_estimada_min": "1"},
        {"tipo_vehiculo": "auto", "distancia_km": "1", "duracion_estimada_min": "1", "multiplicador_demanda": "0.9"},
        {"tipo_vehiculo": "auto", "origen": {"lat": 91, "lng": 0}, "destino": {"lat": 0, "lng": 0}},
    ],
)
def test_estimaciones_invalidas(datos):
    with pytest.raises(ValidationError):
        EstimacionRequest(**datos)


def test_regla_rechaza_negativos_y_mas_de_dos_decimales():
    base = {"tipo_vehiculo": "auto", "precio_por_km": "1", "precio_por_minuto": "1", "tarifa_minima": "1"}
    with pytest.raises(ValidationError):
        ReglaTarifaCreate(**base, tarifa_base="-1")
    with pytest.raises(ValidationError):
        ReglaTarifaCreate(**base, tarifa_base="1.001")


# --- Pagos ------------------------------------------------------------------


def test_pago_requiere_monto_o_estimacion():
    with pytest.raises(ValidationError):
        PagoCreate(**pago(monto=None))
    PagoCreate(**pago(monto=None, estimacion_id=str(uuid4())))


@pytest.mark.parametrize("monto", ["0", "-5", "10.001"])
def test_pago_rechaza_montos_invalidos(monto):
    with pytest.raises(ValidationError):
        PagoCreate(**pago(monto=monto))


def test_captura_y_reembolso_validan_montos():
    CapturaRequest()
    with pytest.raises(ValidationError):
        CapturaRequest(monto="0")
    with pytest.raises(ValidationError):
        ReembolsoCreate(motivo="")


def test_webhook_solo_acepta_aprobado_o_rechazado():
    WebhookPasarela(referencia_externa="x", pago_id=uuid4(), estado="aprobado")
    with pytest.raises(ValidationError):
        WebhookPasarela(referencia_externa="x", pago_id=uuid4(), estado="reembolsado")


# --- Métodos de pago --------------------------------------------------------


def test_tarjeta_valida():
    MetodoPagoCreate(cliente_id=uuid4(), tipo="tarjeta", numero_tarjeta=VISA)


@pytest.mark.parametrize(
    "datos",
    [
        {"tipo": "tarjeta"},
        {"tipo": "tarjeta", "numero_tarjeta": "4111111111111112"},
        {"tipo": "tarjeta", "numero_tarjeta": "4111-1111"},
        {"tipo": "tarjeta", "numero_tarjeta": VISA, "cvv": "123"},
        {"tipo": "tarjeta", "numero_tarjeta": VISA, "proveedor": "mp"},
        {"tipo": "billetera_virtual"},
        {"tipo": "billetera_virtual", "proveedor": "mp", "numero_tarjeta": VISA},
        {"tipo": "efectivo", "proveedor": "mp"},
    ],
)
def test_metodos_de_pago_invalidos(datos):
    with pytest.raises(ValidationError):
        MetodoPagoCreate(cliente_id=uuid4(), **datos)


@pytest.mark.parametrize("numero", [VISA, "5555555555554444", "378282246310005", "4000000000000002", "4000000000000119"])
def test_luhn_acepta_tarjetas_de_prueba(numero):
    assert luhn_valido(numero)


@pytest.mark.parametrize(
    ("numero", "marca"),
    [(VISA, "visa"), ("5555555555554444", "mastercard"), ("2221000000000009", "mastercard"), ("378282246310005", "amex"),
     ("6011111111111117", "otra")],
)
def test_marca_de_tarjeta(numero, marca):
    assert marca_tarjeta(numero) == marca


# --- Liquidaciones y cancelaciones -----------------------------------------


def test_liquidacion_con_periodo_invertido():
    with pytest.raises(ValidationError):
        LiquidacionCreate(beneficiario_id=uuid4(), periodo_desde=date(2026, 2, 1), periodo_hasta=date(2026, 1, 1))


def test_cancelacion_requiere_motivo():
    with pytest.raises(ValidationError):
        CancelacionCreate(viaje_id=uuid4(), cliente_id=uuid4(), motivo="")
