"""API tests for open-source repository intake review gates."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_intake_endpoint_returns_review_plan_without_execution_permission():
    response = client.post("/api/open-source/intake", json={
        "repository_url": "https://github.com/example/project.git",
        "license_id": "Apache-2.0",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["source_url"] == "https://github.com/example/project"
    assert body["license_status"] == "identified_needs_text_review"
    assert body["intake_status"] == "pending_review"
    assert body["reuse_allowed"] is False
    assert body["execution_allowed"] is False
    assert body["auto_merge_allowed"] is False


def test_intake_endpoint_rejects_untrusted_host():
    response = client.post("/api/open-source/intake", json={
        "repository_url": "https://github.com.attacker.invalid/org/repo",
    })
    assert response.status_code == 400


def test_intake_endpoint_validates_request_size():
    response = client.post("/api/open-source/intake", json={
        "repository_url": "https://github.com/" + "x" * 2100,
    })
    assert response.status_code == 422


def test_intake_endpoint_requires_repository_url():
    response = client.post("/api/open-source/intake", json={})
    assert response.status_code == 422
