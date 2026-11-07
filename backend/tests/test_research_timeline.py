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


def test_boolean_limit_rejected():
    import pytest
    with pytest.raises(ValueError, match="limit must be between"):
        build_research_timeline({"bars": sample_bars()}, limit=True)



def test_timeline_indicator_context_respects_warmup_periods():
    from datetime import datetime, timedelta

    bars = []
    start = datetime(2026, 2, 1, tzinfo=__import__("datetime").timezone.utc)
    for i in range(35):
        close = 100 + i * 0.7 + (i % 3) * 0.2
        timestamp = (start + timedelta(days=i)).isoformat().replace("+00:00", "Z")
        bars.append({"timestamp": timestamp,
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


def test_timeline_skips_non_finite_close_change_from_extreme_prices():
    bars = [
        {"timestamp": "2026-01-01T00:00:00Z", "open": 1e-308, "high": 1e-308,
         "low": 1e-308, "close": 1e-308, "volume": 0},
        {"timestamp": "2026-01-02T00:00:00Z", "open": 1e308, "high": 1e308,
         "low": 1e308, "close": 1e308, "volume": 0},
    ]
    report = build_research_timeline({"bars": bars})
    assert report["events"][1]["close_change_pct"] is None


def test_timeline_rejects_duplicate_or_unsorted_timestamps():
    import pytest
    bars = sample_bars()
    bars[3]["timestamp"] = bars[2]["timestamp"]
    with pytest.raises(ValueError, match="timestamps must be unique"):
        build_research_timeline({"bars": bars})
    bars = sample_bars()[::-1]
    with pytest.raises(ValueError, match="sorted chronologically"):
        build_research_timeline({"bars": bars})

def test_timeline_rejects_equivalent_instants_with_different_offsets():
    import pytest
    bars = sample_bars()
    bars[1]["timestamp"] = "2026-01-01T01:00:00+01:00"
    with pytest.raises(ValueError, match="timestamps must be unique"):
        build_research_timeline({"bars": bars})


def test_timeline_rejects_partially_missing_timestamps():
    import pytest
    bars = sample_bars()
    bars[2].pop("timestamp")
    with pytest.raises(ValueError, match="present on every bar or none"):
        build_research_timeline({"bars": bars})


def test_timeline_rejects_naive_timestamps():
    import pytest
    bars = sample_bars()
    bars[0]["timestamp"] = "2026-01-01T00:00:00"
    with pytest.raises(ValueError, match="must include timezone"):
        build_research_timeline({"bars": bars})

def test_swing_observation_is_emitted_on_confirmation_bar_not_pivot_bar():
    bars = sample_bars()
    report = build_research_timeline({"bars": bars})
    # In this fixture, bar 2 is a local high and needs two right-side bars.
    pivot_event = report["events"][2]
    confirmation_event = report["events"][4]
    assert not any(
        item["type"] == "confirmed_swing_high"
        for item in pivot_event["observations"]
    )
    swing = next(
        item for item in confirmation_event["observations"]
        if item["type"] == "confirmed_swing_high"
    )
    assert swing["pivot_index"] == 2
    assert swing["confirmation_index"] == 4
    assert swing["pivot_timestamp"] == bars[2]["timestamp"]
    assert swing["confirmation_timestamp"] == bars[4]["timestamp"]
    assert confirmation_event["timestamp"] == swing["confirmation_timestamp"]


def test_timeline_rejects_non_finite_ohlcv_values():
    import pytest
    bars = sample_bars()
    bars[3]["close"] = float("nan")
    with pytest.raises(ValueError, match="close must be finite"):
        build_research_timeline({"bars": bars})


def test_timeline_rejects_inconsistent_ohlc_and_negative_volume():
    import pytest
    bars = sample_bars()
    bars[0]["low"] = bars[0]["close"] - 2
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
