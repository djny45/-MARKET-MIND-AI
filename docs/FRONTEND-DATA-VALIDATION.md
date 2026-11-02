# Frontend market-data validation

The terminal's **DATA VALIDATION** workspace provides a small UI for checking the shape and basic consistency of a supplied historical OHLCV payload.

## Use the panel

1. Start the backend and frontend using the project's local development instructions.
2. Open the terminal and choose **DATA VALIDATION** in the sidebar.
3. Select **LOAD SAMPLE** to populate a known-good example, or paste your own JSON payload.
4. Select **VALIDATE PAYLOAD**.
5. Inspect the result status, error count, bar count, and returned report. Invalid payloads include field-level error details.

The UI sends a request to `POST /api/market-data/validate`. The request body has a top-level `payload` property:

```json
{
  "payload": {
    "symbol": "BTCUSD",
    "interval": "1d",
    "status": "historical",
    "source": "manual-review",
    "retrieved_at": "2026-01-02T00:00:00Z",
    "bars": [
      {
        "timestamp": "2026-01-01T00:00:00Z",
        "open": 100,
        "high": 105,
        "low": 98,
        "close": 102,
        "volume": 1200
      }
    ]
  }
}
```

## What this checks

The backend validates the payload against the project's market-data contract, including required fields, OHLC consistency, timestamps, and numeric constraints. The report includes validity, error count, bar count, and diagnostic details.

## Important limitations

- This is **structural validation**, not proof that prices are accurate or authentic.
- It does not independently verify provider identity, data licensing, market-session completeness, or whether the data is current.
- A structurally valid payload is not a trading signal or investment recommendation.
- The UI needs the backend API to be running and reachable at the configured API base URL.
- Do not paste API keys, credentials, or other secrets into the payload editor.
