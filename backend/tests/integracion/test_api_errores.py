"""Errores en application/problem+json (RFC 9457), salud y correlación por X-Request-Id."""

from uuid import uuid4

from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app
from app.services.integraciones import obtener_m4

PROBLEMA = "application/problem+json"


def test_validacion_es_400_con_el_detalle_de_cada_campo(client, actores):
    respuesta = client.post(
        "/api/v1/pagos",
        json={"viaje_id": "no-es-uuid", "cliente_id": str(actores.cliente_id), "monto": "-1"},
        headers=actores.cliente,
    )

    assert respuesta.status_code == 400
    assert respuesta.headers["content-type"] == PROBLEMA
    cuerpo = respuesta.json()
    assert (cuerpo["type"], cuerpo["title"], cuerpo["status"]) == ("about:blank", "Solicitud inválida", 400)
    assert cuerpo["instance"] == "/api/v1/pagos"
    campos = {e["campo"] for e in cuerpo["errores"]}
    assert {"body.viaje_id", "body.beneficiario_id", "body.monto"} <= campos


def test_id_de_ruta_invalido_es_400(client, actores):
    assert client.get("/api/v1/pagos/123", headers=actores.operador).status_code == 400


def test_404_generico(client, actores):
    respuesta = client.get(f"/api/v1/liquidaciones/{uuid4()}", headers=actores.operador)

    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json() == {
        "type": "about:blank",
        "title": "No encontrado",
        "status": 404,
        "detail": "Liquidación no encontrada",
        "instance": respuesta.request.url.path,
    }


def test_ruta_inexistente_es_404_sin_detalle(client):
    respuesta = client.get("/api/v1/no-existe")

    assert respuesta.status_code == 404
    assert "detail" not in respuesta.json()


def test_metodo_no_permitido_es_405_con_allow(client, actores):
    respuesta = client.put("/api/v1/pagos", headers=actores.operador)

    assert respuesta.status_code == 405
    assert respuesta.json()["title"] == "Método no permitido"
    assert "GET" in respuesta.headers["Allow"]


def test_error_de_dominio_tiene_type_propio(client, actores):
    respuesta = client.post(f"/api/v1/pagos/{uuid4()}/anulacion", headers=actores.servicio)
    assert respuesta.json()["type"] == "about:blank"

    viaje_id = str(uuid4())
    cuerpo = {"viaje_id": viaje_id, "cliente_id": str(uuid4()), "beneficiario_id": str(uuid4()), "monto": "10"}
    client.post("/api/v1/pagos", json=cuerpo, headers=actores.servicio)
    respuesta = client.post("/api/v1/pagos", json=cuerpo, headers=actores.servicio)

    assert respuesta.status_code == 409
    assert respuesta.json()["title"] == "El viaje ya tiene un cobro vigente"


def test_error_inesperado_es_500_sin_detalles_internos(client, actores):
    def falla():
        raise RuntimeError("detalle interno que no debe salir")

    app.dependency_overrides[obtener_m4] = falla
    respuesta = client.post(
        "/api/v1/tarifas/estimaciones",
        json={"tipo_vehiculo": "auto", "distancia_km": "1", "duracion_estimada_min": "1"},
        headers={**actores.cliente, "X-Request-Id": "req-500"},
    )

    assert respuesta.status_code == 500
    assert respuesta.json()["title"] == "Error interno"
    assert "detalle interno" not in respuesta.text
    assert respuesta.headers["X-Request-Id"] == "req-500"


def test_request_id_se_propaga_o_se_genera(client):
    propagado = client.get("/health", headers={"X-Request-Id": "abc.123_x-y"})
    generado = client.get("/health")
    invalido = client.get("/health", headers={"X-Request-Id": "con espacios!"})

    assert propagado.headers["X-Request-Id"] == "abc.123_x-y"
    assert len(generado.headers["X-Request-Id"]) == 32
    assert invalido.headers["X-Request-Id"] != "con espacios!"


def test_errores_tambien_devuelven_request_id(client):
    assert client.get("/api/v1/pagos", headers={"X-Request-Id": "r-401"}).headers["X-Request-Id"] == "r-401"


def test_health(client):
    respuesta = client.get("/health")

    assert (respuesta.status_code, respuesta.json()) == (200, {"estado": "ok"})


def test_health_sin_base_es_503(client):
    class SesionCaida:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("sin conexión"))

    app.dependency_overrides[get_db] = lambda: SesionCaida()
    respuesta = client.get("/health")

    assert respuesta.status_code == 503
    assert respuesta.json()["title"] == "Servicio no disponible"
