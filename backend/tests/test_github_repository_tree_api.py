"""API contract tests for the open-source tree scanner."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.github_repository_crawler import GitHubCrawlerError

client = TestClient(app)


def test_tree_scan_endpoint_returns_manifest():
    payload = {
        "pinned_commit_sha": "a" * 40,
        "entry_count": 1,
        "dependency_manifests": ["pyproject.toml"],
        "scanner_policy": {"repository_code_executed": False},
    }
    with patch("app.main.scan_repository_tree", return_value=payload) as scan:
        response = client.post("/api/open-source/scan-tree", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 200
    assert response.json()["pinned_commit_sha"] == "a" * 40
    scan.assert_called_once_with("https://github.com/example/project")


def test_tree_scan_endpoint_rejects_invalid_url():
    response = client.post("/api/open-source/scan-tree", json={
        "repository_url": "https://github.com.evil.example/example/project",
    })
    assert response.status_code == 400


def test_tree_scan_endpoint_maps_upstream_error():
    with patch("app.main.scan_repository_tree", side_effect=GitHubCrawlerError("tree unavailable")):
        response = client.post("/api/open-source/scan-tree", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 502
    assert response.json()["detail"] == "tree unavailable"
