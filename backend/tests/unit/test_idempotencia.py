from uuid import uuid4

import pytest

from app.core.errors import ErrorDominio
from app.db.models import ClaveIdempotencia
from app.services.idempotencia import hash_cuerpo, verificar


def registro(cuerpo: dict) -> ClaveIdempotencia:
    return ClaveIdempotencia(operacion="pago", clave="k", hash_cuerpo=hash_cuerpo(cuerpo), recurso_id=uuid4())


def test_el_hash_no_depende_del_orden_de_las_claves():
    assert hash_cuerpo({"a": 1, "b": "x"}) == hash_cuerpo({"b": "x", "a": 1})


def test_el_hash_cambia_con_el_contenido():
    assert hash_cuerpo({"monto": "100"}) != hash_cuerpo({"monto": "101"})


def test_clave_nueva():
    assert verificar(None, hash_cuerpo({"monto": "100"})) is None


def test_misma_clave_mismo_cuerpo_devuelve_el_recurso_original():
    existente = registro({"monto": "100"})

    assert verificar(existente, hash_cuerpo({"monto": "100"})) == existente.recurso_id


def test_misma_clave_otro_cuerpo_es_422():
    existente = registro({"monto": "100"})

    with pytest.raises(ErrorDominio) as error:
        verificar(existente, hash_cuerpo({"monto": "999"}))

    assert error.value.status_code == 422
    assert error.value.tipo == "/errores/idempotency-key-reutilizada"
