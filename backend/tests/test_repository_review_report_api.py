"""API tests for the static open-source review report."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.github_repository_crawler import GitHubCrawlerError

client = TestClient(app)


def test_review_report_endpoint_returns_static_report():
    payload = {"pinned_commit_sha": "a" * 40, "analysis_policy": {"license_approved": False}}
    with patch("app.main.build_repository_review_report", return_value=payload) as build:
        response = client.post("/api/open-source/review-report", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 200
    assert response.json()["analysis_policy"]["license_approved"] is False
    build.assert_called_once_with("https://github.com/example/project")


def test_review_report_endpoint_rejects_bad_url():
    response = client.post("/api/open-source/review-report", json={
        "repository_url": "https://github.com.attacker.invalid/org/repo",
    })
    assert response.status_code == 400


def test_review_report_endpoint_maps_upstream_error():
    with patch("app.main.build_repository_review_report", side_effect=GitHubCrawlerError("upstream unavailable")):
        response = client.post("/api/open-source/review-report", json={
            "repository_url": "https://github.com/example/project",
        })
    assert response.status_code == 502
