"""Session-aware historical gap diagnostics using an explicit operator-supplied calendar."""
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

INTERVAL_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


def _parse_time(value):
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("session times must use HH:MM format") from None


def _parse_timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def build_session_gap_report(history, calendar):
    """Count missing scheduled bar starts per source; never infer holidays or sessions."""
    interval = history.get("interval")
    if interval not in INTERVAL_SECONDS:
        raise ValueError("unsupported interval; expected 15m, 1h, 4h or 1d")
    if not isinstance(calendar, dict):
        raise ValueError("calendar must be an object")
    try:
        zone = ZoneInfo(calendar["timezone"])
    except (KeyError, ZoneInfoNotFoundError, TypeError):
        raise ValueError("calendar timezone must be a valid IANA timezone") from None

    weekdays = calendar.get("weekdays")
    if not isinstance(weekdays, list) or not weekdays or any(
        isinstance(day, bool) or not isinstance(day, int) or day < 0 or day > 6 for day in weekdays
    ) or len(set(weekdays)) != len(weekdays):
        raise ValueError("weekdays must be unique integers from 0 (Monday) to 6 (Sunday)")
    opening = _parse_time(calendar.get("session_open"))
    closing = _parse_time(calendar.get("session_close"))
    if opening >= closing:
        raise ValueError("overnight sessions are not supported; session_close must follow session_open")
    holidays = calendar.get("holidays", [])
    if not isinstance(holidays, list) or len(holidays) > 1000:
        raise ValueError("holidays must be a list of at most 1000 ISO dates")
    try:
        holiday_dates = {date.fromisoformat(item) for item in holidays}
    except (TypeError, ValueError):
        raise ValueError("holidays must contain ISO dates (YYYY-MM-DD)") from None

    parsed = []
    invalid_timestamps = []
    for index, bar in enumerate(history.get("bars", [])):
        instant = _parse_timestamp(bar.get("timestamp"))
        if instant is None:
            invalid_timestamps.append({"bar_index": index, "timestamp": bar.get("timestamp")})
        else:
            parsed.append((index, bar, instant))
    if not parsed:
        return {
            "symbol": history.get("symbol"), "interval": interval,
            "calendar_name": calendar.get("name", "operator_supplied"),
            "timezone": calendar["timezone"], "status": "insufficient_timestamps",
            "source_reports": {}, "invalid_timestamps": invalid_timestamps,
            "methodology": ["No expected schedule is inferred without at least one timezone-aware observation."],
        }

    local_dates = [instant.astimezone(zone).date() for _, _, instant in parsed]
    first_day, last_day = min(local_dates), max(local_dates)
    interval_seconds = INTERVAL_SECONDS[interval]
    expected_by_day = {}
    current_day = first_day
    while current_day <= last_day:
        if current_day.weekday() in weekdays and current_day not in holiday_dates:
            local_open = datetime.combine(current_day, opening, tzinfo=zone)
            local_close = datetime.combine(current_day, closing, tzinfo=zone)
            expected = []
            cursor = local_open
            if interval == "1d":
                expected.append(local_open.astimezone(timezone.utc))
            else:
                while cursor + timedelta(seconds=interval_seconds) <= local_close:
                    expected.append(cursor.astimezone(timezone.utc))
                    cursor += timedelta(seconds=interval_seconds)
            expected_by_day[current_day] = set(expected)
        current_day += timedelta(days=1)

    expected_all = set().union(*expected_by_day.values()) if expected_by_day else set()
    by_source = {}
    for index, bar, instant in parsed:
        source = str(bar.get("source") or "unknown")
        report = by_source.setdefault(source, {
            "observed_count": 0, "outside_schedule_count": 0,
            "duplicate_timestamp_count": 0, "_seen": set(), "_matched": set(),
        })
        report["observed_count"] += 1
        if instant in report["_seen"]:
            report["duplicate_timestamp_count"] += 1
        report["_seen"].add(instant)
        if instant in expected_all:
            report["_matched"].add(instant)
        else:
            report["outside_schedule_count"] += 1

    source_reports = {}
    for source, report in sorted(by_source.items()):
        missing = sorted(expected_all - {
            instant for _, bar, instant in parsed
            if str(bar.get("source") or "unknown") == source
        })
        source_reports[source] = {
            "observed_count": report["observed_count"],
            "expected_scheduled_count": len(expected_all),
            "matched_scheduled_count": len(report["_matched"]),
            "missing_scheduled_count": len(missing),
            "outside_schedule_count": report["outside_schedule_count"],
            "duplicate_timestamp_count": report["duplicate_timestamp_count"],
            "missing_examples_utc": [item.isoformat() for item in missing[:100]],
        }

    return {
        "symbol": history.get("symbol"), "interval": interval,
        "calendar_name": calendar.get("name", "operator_supplied"),
        "market": calendar.get("market", "unspecified"),
        "timezone": calendar["timezone"],
        "date_range_local": {"start": first_day.isoformat(), "end": last_day.isoformat()},
        "scheduled_session_days": len(expected_by_day),
        "expected_scheduled_bar_count": len(expected_all),
        "invalid_timestamp_count": len(invalid_timestamps),
        "invalid_timestamps": invalid_timestamps,
        "source_reports": source_reports,
        "methodology": [
            "The session calendar, timezone, weekdays and holiday dates are supplied by the operator.",
            "No exchange holiday, early close, auction, daylight-saving exception or venue schedule is fetched or inferred.",
            "Intraday expected bars are bar-start timestamps for complete intervals fully contained in the session; daily bars are scheduled at session open.",
            "Overnight sessions and intraday breaks are not modelled.",
            "Missing scheduled observations are diagnostics, not proof of provider failure or market-data unavailability.",
        ],
    }
