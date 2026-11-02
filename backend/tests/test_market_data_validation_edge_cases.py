from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_validation_endpoint_reports_non_object_payload():
    response = client.post(
        "/api/market-data/validate",
        json={"payload": ["not", "an", "object"]},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["valid"] is False
    assert report["result"] == "invalid"
    assert report["error_count"] > 0
    assert report["errors"]


def test_validation_endpoint_returns_422_when_payload_is_missing():
    response = client.post("/api/market-data/validate", json={})

    assert response.status_code == 422
    assert response.json()["detail"]
