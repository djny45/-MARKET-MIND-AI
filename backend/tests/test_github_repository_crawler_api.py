"""API tests for metadata-only public GitHub crawling."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.github_repository_crawler import GitHubCrawlerError

client = TestClient(app)


def test_metadata_crawler_endpoint_returns_pinned_commit():
    payload = {
        "source_url": "https://github.com/example/project",
        "pinned_commit": {"sha": "a" * 40},
        "crawler_policy": {"metadata_only": True, "code_executed": False},
    }
    with patch("app.main.fetch_repository_metadata", return_value=payload) as fetch:
        response = client.post("/api/open-source/crawl-metadata", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 200
    assert response.json()["pinned_commit"]["sha"] == "a" * 40
    fetch.assert_called_once_with("https://github.com/example/project")


def test_metadata_crawler_endpoint_rejects_invalid_repository_url():
    response = client.post("/api/open-source/crawl-metadata", json={
        "repository_url": "https://github.com.attacker.invalid/org/repo",
    })
    assert response.status_code == 400


def test_metadata_crawler_endpoint_maps_upstream_failure_to_502():
    with patch("app.main.fetch_repository_metadata", side_effect=GitHubCrawlerError("upstream unavailable")):
        response = client.post("/api/open-source/crawl-metadata", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream unavailable"
