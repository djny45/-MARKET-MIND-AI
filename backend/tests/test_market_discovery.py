from datetime import datetime, timezone, timedelta

from app.market_discovery import MarketCandidate, prioritize_for_research


NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def candidate(symbol="ABC", **kwargs):
    data = dict(
        symbol=symbol, venue="TEST", asset_class="equity", source="fixture",
        observed_at=NOW.isoformat(), data_available=True, data_quality=0.9,
        activity=0.8, volatility=0.5, news_attention=0.4,
        social_attention=0.3, timeframes=("1h", "1d"),
    )
    data.update(kwargs)
    return MarketCandidate(**data)


def test_priority_is_transparent_and_bounded():
    result = prioritize_for_research([candidate()], now=NOW)
    assert len(result) == 1
    assert 0 <= result[0].score <= 1
    assert result[0].confidence == "high"
    assert "activity=0.80" in result[0].reasons


def test_missing_optional_evidence_is_renormalized_and_disclosed():
    result = prioritize_for_research(
        [candidate(news_attention=None, social_attention=None)], now=NOW
    )[0]
    assert "news_attention" in result.missing_evidence
    assert "social_attention" in result.missing_evidence
    assert result.confidence == "medium"


def test_stale_or_unavailable_candidates_are_excluded():
    stale = candidate(observed_at=(NOW - timedelta(hours=30)).isoformat())
    unavailable = candidate("XYZ", data_available=False)
    assert prioritize_for_research([stale, unavailable], now=NOW) == []


def test_invalid_timestamp_and_missing_quality_are_excluded():
    bad_time = candidate(observed_at="not-a-date")
    no_quality = candidate("QWE", data_quality=None)
    assert prioritize_for_research([bad_time, no_quality], now=NOW) == []


def test_duplicate_symbols_are_deduped_and_limit_applies():
    result = prioritize_for_research(
        [candidate(), candidate(activity=0.1), candidate("DEF")], now=NOW, limit=1
    )
    assert len(result) == 1
    assert result[0].symbol == "ABC"


def test_invalid_limit_rejected():
    try:
        prioritize_for_research([], now=NOW, limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("expected ValueError")
