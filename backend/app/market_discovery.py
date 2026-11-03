"""Evidence-aware market discovery for autonomous research prioritization.

This module selects *what to research*, not what to buy or sell. It is
provider-neutral: adapters supply candidate metadata; this module never
scrapes websites or invents market data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional


@dataclass(frozen=True)
class MarketCandidate:
    symbol: str
    venue: str
    asset_class: str
    source: str
    observed_at: str
    data_available: bool
    data_quality: float = 0.0
    activity: Optional[float] = None
    volatility: Optional[float] = None
    news_attention: Optional[float] = None
    social_attention: Optional[float] = None
    timeframes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchPriority:
    symbol: str
    venue: str
    score: float
    confidence: str
    reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    source: str
    observed_at: str
    timeframes: tuple[str, ...]


def _bounded(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN
        return None
    return max(0.0, min(1.0, value))


def prioritize_for_research(
    candidates: Iterable[MarketCandidate],
    *,
    now: Optional[datetime] = None,
    max_age_hours: float = 24.0,
    limit: int = 25,
) -> list[ResearchPriority]:
    """Return a transparent research queue, excluding stale/unavailable data.

    Inputs are normalized 0..1 provider measurements. Missing values are
    omitted and weights are renormalized; missingness lowers confidence.
    This is not an investment ranking or a prediction.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be > 0")
    now = now or datetime.now(timezone.utc)
    weights = {
        "data_quality": 0.35,
        "activity": 0.20,
        "volatility": 0.15,
        "news_attention": 0.15,
        "social_attention": 0.15,
    }
    output: list[ResearchPriority] = []
    seen: set[tuple[str, str]] = set()

    for c in candidates:
        key = (c.venue.strip().lower(), c.symbol.strip().upper())
        if not c.symbol.strip() or not c.venue.strip() or key in seen:
            continue
        seen.add(key)
        if not c.data_available:
            continue
        try:
            stamp = datetime.fromisoformat(c.observed_at.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (now - stamp.astimezone(timezone.utc)).total_seconds() / 3600
        except (ValueError, TypeError, AttributeError):
            continue
        if age < -1 or age > max_age_hours:
            continue

        values = {name: _bounded(getattr(c, name)) for name in weights}
        # Data quality is required. Do not rank candidates with no quality evidence.
        if values["data_quality"] is None:
            continue
        present = {k: v for k, v in values.items() if v is not None}
        denom = sum(weights[k] for k in present)
        score = sum(weights[k] * v for k, v in present.items()) / denom
        missing = tuple(k for k in weights if values[k] is None)
        reasons = tuple(
            f"{k}={v:.2f}" for k, v in present.items()
        ) + (f"data_age_hours={age:.1f}",)
        confidence = "high" if len(missing) == 0 and age <= 2 else (
            "medium" if len(missing) <= 2 and age <= 12 else "low"
        )
        output.append(ResearchPriority(
            symbol=c.symbol.strip().upper(),
            venue=c.venue.strip(),
            score=round(score, 4),
            confidence=confidence,
            reasons=reasons,
            missing_evidence=missing,
            source=c.source,
            observed_at=c.observed_at,
            timeframes=c.timeframes,
        ))

    return sorted(output, key=lambda x: (-x.score, x.symbol, x.venue))[:limit]


def priorities_as_dict(items: Iterable[ResearchPriority]) -> list[dict]:
    """Serialize research queue entries for API/CLI consumers."""
    return [asdict(item) for item in items]
