"""API tests for dependency compatibility reports."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_compatibility_report_endpoint_returns_review_only_report():
    response = client.post("/api/open-source/compatibility-report", json={
        "candidate_report": {
            "source_url": "https://github.com/example/repo",
            "pinned_commit_sha": "abc123",
            "dependencies": [{"name": "numpy", "specifier": ">=1", "source_file": "requirements.txt"}],
        },
        "project_dependencies": [{"name": "NumPy", "specifier": ">=1.20", "source_file": "backend/requirements.txt"}],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["name_overlap_count"] == 1
    assert body["approval"]["install_allowed"] is False


def test_compatibility_report_rejects_wrong_payload_type():
    response = client.post("/api/open-source/compatibility-report", json={
        "candidate_report": [],
        "project_dependencies": [],
    })
    assert response.status_code == 400
