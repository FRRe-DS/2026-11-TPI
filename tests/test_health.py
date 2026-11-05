from unittest.mock import MagicMock
from sqlalchemy.exc import OperationalError

from app.db.session import get_db


def test_health_check_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data


def test_health_check_db_error(client):
    broken_session = MagicMock()
    broken_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("DB down"))
    client.app.dependency_overrides[get_db] = lambda: broken_session

    response = client.get("/health")
    assert response.status_code == 503
    assert "no está disponible" in response.json()["detail"]
