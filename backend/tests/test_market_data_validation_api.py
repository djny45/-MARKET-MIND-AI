from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_market_data_validation_endpoint_returns_valid_report():
    response = client.post("/api/market-data/validate", json={
        "payload": {
            "symbol": "BTCUSD",
            "interval": "1d",
            "status": "historical",
            "source": "provider-x",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "bars": [{
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
            }],
        }
    })

    assert response.status_code == 200
    report = response.json()
    assert report["valid"] is True
    assert report["result"] == "valid"
    assert report["error_count"] == 0
    assert report["bar_count"] == 1


def test_market_data_validation_endpoint_reports_invalid_payload():
    response = client.post("/api/market-data/validate", json={
        "payload": {
            "symbol": "BTCUSD",
            "interval": "1d",
            "status": "historical",
            "source": "provider-x",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "bars": [{
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 8, "low": 9, "close": 11, "volume": 100,
            }],
        }
    })

    assert response.status_code == 200
    report = response.json()
    assert report["valid"] is False
    assert report["result"] == "invalid"
    assert report["error_count"] == len(report["errors"])
    assert report["errors"]
