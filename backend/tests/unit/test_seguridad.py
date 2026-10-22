from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import (
    Usuario,
    filtro_propio,
    get_usuario,
    require_scope,
    usuario_desde_claims,
    verificar_beneficiario,
    verificar_cliente,
    verificar_pago_visible,
)


def credencial(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def usuario(*roles: str, sub=None, scopes=("*",)) -> Usuario:
    return Usuario(sub=str(sub or uuid4()), roles=frozenset(roles), scopes=frozenset(scopes))


# --- Validación del token ---------------------------------------------------


def test_token_valido(emitir_token):
    sub = str(uuid4())

    resultado = get_usuario(credencial(emitir_token(sub=sub, roles=("CLIENTE", "offline_access"))))

    assert resultado.sub == sub
    assert resultado.roles == {"cliente"}
    assert "pagos:read" in resultado.scopes


def test_sin_token_es_401():
    with pytest.raises(HTTPException) as error:
        get_usuario(None)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize(
    "alteracion",
    [
        {"aud": "otro-modulo"},
        {"iss": "http://otro-issuer/realms/x"},
        {"vence_en": timedelta(seconds=-1)},
    ],
)
def test_token_con_claims_invalidos_es_401(emitir_token, alteracion):
    with pytest.raises(HTTPException) as error:
        get_usuario(credencial(emitir_token(**alteracion)))

    assert error.value.status_code == 401


def test_token_firmado_con_otra_clave_es_401(emitir_token):
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(HTTPException) as error:
        get_usuario(credencial(emitir_token(clave=otra)))

    assert error.value.status_code == 401


def test_token_malformado_es_401():
    with pytest.raises(HTTPException) as error:
        get_usuario(credencial("no-es-un-jwt"))

    assert error.value.status_code == 401


def test_auth_deshabilitada_actua_como_operador(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)

    resultado = get_usuario(None)

    assert resultado.ve_todo and "*" in resultado.scopes


def test_roles_ajenos_a_m7_se_ignoran():
    assert usuario_desde_claims({"sub": "x", "realm_access": {"roles": ["uma_authorization"]}}).roles == set()


def test_sub_no_uuid():
    assert usuario_desde_claims({"sub": "service-account-m5"}).id is None


# --- Scopes y roles ---------------------------------------------------------


def test_require_scope_acepta_el_scope_entre_varios():
    u = usuario("cliente", scopes=("openid", "pagos:read", "pagos:write"))

    assert require_scope("pagos:write")(u) is u


def test_require_scope_rechaza_si_falta():
    with pytest.raises(HTTPException) as error:
        require_scope("pagos:write")(usuario("cliente", scopes=("pagos:read",)))

    assert error.value.status_code == 403


def test_require_scope_exige_el_rol():
    with pytest.raises(HTTPException) as error:
        require_scope("tarifas:write", "operador")(usuario("servicio"))

    assert error.value.status_code == 403
    assert require_scope("tarifas:write", "operador")(usuario("operador"))


# --- Propiedad --------------------------------------------------------------


def test_cliente_solo_opera_sobre_si_mismo():
    yo = uuid4()
    verificar_cliente(usuario("cliente", sub=yo), yo)
    with pytest.raises(HTTPException):
        verificar_cliente(usuario("cliente", sub=yo), uuid4())


def test_conductor_no_opera_como_cliente():
    yo = uuid4()
    with pytest.raises(HTTPException):
        verificar_cliente(usuario("conductor", sub=yo), yo)


@pytest.mark.parametrize("rol", ["operador", "servicio"])
def test_operador_y_servicio_ven_todo(rol):
    verificar_cliente(usuario(rol), uuid4())
    verificar_beneficiario(usuario(rol), uuid4())
    verificar_pago_visible(usuario(rol), uuid4(), uuid4())


def test_conductor_solo_ve_lo_propio():
    yo = uuid4()
    verificar_beneficiario(usuario("conductor", sub=yo), yo)
    with pytest.raises(HTTPException):
        verificar_beneficiario(usuario("conductor", sub=yo), uuid4())
    with pytest.raises(HTTPException):
        verificar_beneficiario(usuario("cliente", sub=yo), yo)


def test_pago_visible_para_su_cliente_y_su_beneficiario():
    cliente, chofer = uuid4(), uuid4()
    verificar_pago_visible(usuario("cliente", sub=cliente), cliente, chofer)
    verificar_pago_visible(usuario("conductor", sub=chofer), cliente, chofer)
    with pytest.raises(HTTPException):
        verificar_pago_visible(usuario("cliente"), cliente, chofer)


def test_filtro_propio_fuerza_el_id_del_usuario():
    yo = uuid4()

    assert filtro_propio(usuario("cliente", sub=yo), None, None) == (yo, None)
    assert filtro_propio(usuario("conductor", sub=yo), None, None) == (None, yo)
    otro = uuid4()
    assert filtro_propio(usuario("operador"), otro, None) == (otro, None)


def test_filtro_propio_rechaza_pedir_datos_ajenos():
    with pytest.raises(HTTPException):
        filtro_propio(usuario("cliente"), uuid4(), None)
    with pytest.raises(HTTPException):
        filtro_propio(usuario("conductor"), None, uuid4())
    with pytest.raises(HTTPException):
        filtro_propio(usuario(), None, None)
