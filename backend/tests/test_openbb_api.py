"""API contract tests for the restricted OpenBB CLI endpoints."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openbb_status_reports_installation_and_gate():
    with patch("app.main.shutil.which", return_value="/usr/bin/openbb", create=True), \
         patch("app.main.openbb_cli_enabled", return_value=False):
        response = client.get("/api/openbb/status")

    assert response.status_code == 200
    assert response.json() == {
        "installed": True,
        "enabled": False,
        "mode": "restricted-informational-cli",
    }


def test_openbb_cli_endpoint_returns_adapter_result_without_extra_fields():
    adapter_result = type("Result", (), {
        "available": False,
        "action": "help",
        "exit_code": None,
        "output": "",
        "error": "OpenBB CLI execution is disabled.",
    })()

    with patch("app.main.run_openbb_cli", return_value=adapter_result) as run:
        response = client.post("/api/openbb/cli", json={"action": "help"})

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "action": "help",
        "exit_code": None,
        "output": "",
        "error": "OpenBB CLI execution is disabled.",
    }
    run.assert_called_once_with("help")


def test_openbb_cli_endpoint_rejects_arbitrary_actions():
    response = client.post("/api/openbb/cli", json={"action": "exec"})

    assert response.status_code == 422
