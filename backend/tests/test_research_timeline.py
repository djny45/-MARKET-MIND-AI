from app.research_timeline import build_research_timeline


def sample_bars():
    closes = [10, 11, 13, 12, 10, 9, 11, 12, 10, 8, 9, 11]
    return [{"timestamp": f"2026-01-{i+1:02d}T00:00:00+00:00",
             "open": c - 0.2, "high": c + 0.5, "low": c - 0.5,
             "close": c, "volume": 100 + i, "source": "fixture",
             "status": "synthetic", "retrieved_at": "2026-01-20T00:00:00Z"}
            for i, c in enumerate(closes)]


def test_timeline_preserves_timestamp_and_provenance():
    report = build_research_timeline({"symbol": "BTCUSD", "interval": "1h", "bars": sample_bars()})
    assert report["bars_included"] == 12
    assert report["events"][0]["timestamp"].startswith("2026-01-01")
    assert report["events"][0]["source"] == "fixture"
    assert report["events"][0]["status"] == "synthetic"
    assert report["execution"] == "disabled"


def test_timeline_limit_returns_latest_events():
    report = build_research_timeline({"bars": sample_bars()}, limit=3)
    assert len(report["events"]) == 3
    assert report["events"][-1]["index"] == 11


def test_empty_timeline_is_explicit():
    report = build_research_timeline({"bars": []})
    assert report["status"] == "no_stored_observations"
    assert report["events"] == []


def test_invalid_limit_rejected():
    import pytest
    with pytest.raises(ValueError):
        build_research_timeline({"bars": sample_bars()}, limit=1001)



def test_timeline_indicator_context_respects_warmup_periods():
    bars = []
    for i in range(35):
        close = 100 + i * 0.7 + (i % 3) * 0.2
        bars.append({"timestamp": f"2026-02-{i+1:02d}T00:00:00Z",
                     "open": close - 0.1, "high": close + 0.5,
                     "low": close - 0.5, "close": close,
                     "volume": 1000, "source": "fixture", "status": "synthetic"})
    report = build_research_timeline({"bars": bars})
    early = report["events"][0]["indicator_context"]
    mature = report["events"][-1]["indicator_context"]
    assert early["sma20"] is None
    assert early["rsi14"] is None
    assert mature["sma20"] is not None
    assert mature["rsi14"] is not None
    assert set(mature) == {"sma20", "rsi14", "macd", "macd_signal", "macd_histogram"}


def test_timeline_rejects_non_finite_ohlcv_values():
    import pytest
    bars = sample_bars()
    bars[3]["close"] = float("nan")
    with pytest.raises(ValueError, match="close must be finite"):
        build_research_timeline({"bars": bars})


def test_timeline_rejects_inconsistent_ohlc_and_negative_volume():
    import pytest
    bars = sample_bars()
    bars[0]["high"] = bars[0]["close"] - 1
    with pytest.raises(ValueError, match="high must be >= open and close"):
        build_research_timeline({"bars": bars})
    bars = sample_bars()
    bars[0]["volume"] = -1
    with pytest.raises(ValueError, match="volume must be non-negative"):
        build_research_timeline({"bars": bars})


def test_timeline_rejects_boolean_as_numeric_ohlcv():
    import pytest
    bars = sample_bars()
    bars[0]["open"] = True
    with pytest.raises(ValueError, match="open must be numeric"):
        build_research_timeline({"bars": bars})
