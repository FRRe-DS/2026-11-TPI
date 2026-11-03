def test_error_404_ruta_inexistente(client):
    """Verifica que una ruta inexistente devuelva 404 en formato RFC 9457."""
    response = client.get("/ruta-que-no-existe")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert "X-Request-Id" in response.headers

    data = response.json()
    assert data["type"] == "about:blank"
    assert data["title"] == "No encontrado"
    assert data["status"] == 404
    assert data["instance"] == "/ruta-que-no-existe"


def test_error_405_metodo_no_permitido(client):
    """Verifica que un método no admitido devuelva 405 y el encabezado Allow."""
    # /health solo admite GET, probamos con POST
    response = client.post("/health")
    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"
    assert "X-Request-Id" in response.headers
    assert "Allow" in response.headers

    data = response.json()
    assert data["type"] == "about:blank"
    assert data["title"] == "Método no permitido"
    assert data["status"] == 405


def test_propagacion_x_request_id_cliente(client):
    """Verifica que si el cliente envía un X-Request-Id válido, la API lo devuelva."""
    custom_id = "mi-request-id-12345"
    response = client.get("/ruta-que-no-existe", headers={"X-Request-Id": custom_id})
    assert response.headers["X-Request-Id"] == custom_id


def test_generacion_x_request_id_si_es_invalido_o_falta(client):
    """Verifica que si no se envía X-Request-Id o tiene caracteres inválidos, se genere uno nuevo."""
    # Caracteres no permitidos (espacios, arrobas, etc.)
    response = client.get("/ruta-que-no-existe", headers={"X-Request-Id": "invalido con espacios @#!"})
    assert "X-Request-Id" in response.headers
    assert response.headers["X-Request-Id"] != "invalido con espacios @#!"


def test_error_415_content_type_no_soportado(client):
    """Verifica que un POST con Content-Type distinto a application/json responda 415."""
    response = client.post(
        "/tarifas/estimar",
        content="texto plano",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
    assert response.headers["content-type"] == "application/problem+json"

    data = response.json()
    assert data["type"] == "about:blank"
    assert data["title"] == "Tipo de contenido no soportado"
    assert data["status"] == 415


def test_error_400_validacion_pydantic_formato_invalido(client):
    """Verifica que un JSON con tipos de datos inválidos responda 400 Solicitud inválida."""
    # distancia_km debe ser float, le mandamos un string inválido
    response = client.post(
        "/tarifas/estimar",
        json={"tipo_vehiculo": "auto", "distancia_km": "esto_no_es_un_numero", "tiempo_min": 10},
    )
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"

    data = response.json()
    assert data["type"] == "about:blank"
    assert data["title"] == "Solicitud inválida"
    assert data["status"] == 400

