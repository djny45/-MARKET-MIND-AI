"""API tests for bounded review-file retrieval."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.github_repository_crawler import GitHubCrawlerError

client = TestClient(app)


def test_review_files_endpoint_returns_only_review_payload():
    payload = {
        "pinned_commit_sha": "a" * 40,
        "retrieved_file_count": 1,
        "files": [{"path": "README.md", "content": "# docs"}],
    }
    with patch("app.main.fetch_review_files", return_value=payload) as fetch:
        response = client.post("/api/open-source/scan-review-files", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 200
    assert response.json()["files"][0]["path"] == "README.md"
    fetch.assert_called_once_with("https://github.com/example/project")


def test_review_files_endpoint_rejects_invalid_url():
    response = client.post("/api/open-source/scan-review-files", json={
        "repository_url": "https://github.com.evil.example/example/project",
    })
    assert response.status_code == 400


def test_review_files_endpoint_maps_upstream_error():
    with patch("app.main.fetch_review_files", side_effect=GitHubCrawlerError("file fetch failed")):
        response = client.post("/api/open-source/scan-review-files", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 502
    assert response.json()["detail"] == "file fetch failed"
