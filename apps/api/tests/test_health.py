from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_exact_contract() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "portfolio-dss-api",
        "version": "0.4.0",
    }
