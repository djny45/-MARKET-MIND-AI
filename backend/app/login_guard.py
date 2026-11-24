"""Failed-login throttling and lockout for the credential endpoint.

Password verification uses scrypt, but nothing limited how often a caller could
try: `RateLimitMiddleware` is disabled unless an operator sets
`API_RATE_LIMIT_PER_MINUTE`, so a default deployment accepted unlimited login
attempts. Guessing is therefore the cheapest way into a research deployment.

This guard counts failures per account and per client address in a sliding
window, and locks the pair out with exponential backoff once the threshold is
reached. It is deliberately in-process: the platform is single-host (see
ADR-0001), and a shared store would be a distributed-systems promise this
architecture does not make. Restarts clear the counters, which is the honest
trade: an attacker cannot escalate a lockout, and an operator can always recover
access.

Knobs:

* ``MARKET_MIND_LOGIN_MAX_FAILURES`` — failures inside one window before
  lockout (default 5).
* ``MARKET_MIND_LOGIN_WINDOW_SECONDS`` — sliding window length (default 900).
* ``MARKET_MIND_LOGIN_LOCKOUT_SECONDS`` — first lockout length, doubled per
  further failure up to ``WINDOW`` (default 300).
"""
from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable

_DEFAULTS = {"max_failures": 5, "window_seconds": 900, "lockout_seconds": 300}
# Hard ceiling on tracked keys so a hostile client cannot grow this dict without
# bound by rotating usernames or source addresses.
MAX_TRACKED_KEYS = 4096


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def settings() -> dict[str, int]:
    """Return the configured thresholds."""
    return {
        "max_failures": _env_int("MARKET_MIND_LOGIN_MAX_FAILURES",
                                 _DEFAULTS["max_failures"], minimum=1),
        "window_seconds": _env_int("MARKET_MIND_LOGIN_WINDOW_SECONDS",
                                   _DEFAULTS["window_seconds"], minimum=1),
        "lockout_seconds": _env_int("MARKET_MIND_LOGIN_LOCKOUT_SECONDS",
                                    _DEFAULTS["lockout_seconds"], minimum=1),
    }


@dataclass
class _Entry:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0
    lockouts: int = 0


class LoginGuard:
    """Sliding-window failure counter with exponential lockout."""

    def __init__(self, *, clock: Callable[[], float] | None = None,
                 max_tracked_keys: int = MAX_TRACKED_KEYS):
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self.max_tracked_keys = max_tracked_keys

    # -- internals -------------------------------------------------------
    def _config(self) -> dict[str, int]:
        return settings()

    def _key(self, username: str, client: str) -> str:
        return f"{(username or '').strip().lower()}|{(client or 'unknown').strip()}"

    def _entry(self, key: str) -> _Entry:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
            return entry
        now = self._clock()
        window = self._config()["window_seconds"]
        # Prefer dropping entries that can no longer affect a decision.
        for old_key, old_entry in list(self._entries.items()):
            if old_entry.locked_until <= now:
                self._prune(old_entry, now, window)
                if not old_entry.failures:
                    self._entries.pop(old_key, None)
        while len(self._entries) >= self.max_tracked_keys:
            victim = next(
                (name for name, value in self._entries.items() if value.locked_until <= now),
                None,
            )
            if victim is None:
                # Never evict an active lockout to track an unrelated key.
                return _Entry()
            self._entries.pop(victim)
        entry = _Entry()
        self._entries[key] = entry
        return entry

    def _prune(self, entry: _Entry, now: float, window: int) -> None:
        horizon = now - window
        entry.failures = [stamp for stamp in entry.failures if stamp >= horizon]

    # -- public API ------------------------------------------------------
    def check(self, username: str, client: str = "") -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)`` without recording a try."""
        config = self._config()
        entry = self._entries.get(self._key(username, client))
        if entry is None:
            return True, 0
        now = self._clock()
        if entry.locked_until > now:
            return False, max(1, int(round(entry.locked_until - now)))
        self._prune(entry, now, config["window_seconds"])
        return True, 0

    def record_failure(self, username: str, client: str = "") -> dict:
        """Record a failed attempt and lock out once the threshold is crossed."""
        config = self._config()
        now = self._clock()
        entry = self._entry(self._key(username, client))
        self._prune(entry, now, config["window_seconds"])
        entry.failures.append(now)
        result = {"failures": len(entry.failures), "locked_for": 0}
        if len(entry.failures) >= config["max_failures"]:
            entry.lockouts += 1
            duration = min(config["window_seconds"],
                           config["lockout_seconds"] * (2 ** (entry.lockouts - 1)))
            entry.locked_until = now + duration
            entry.failures.clear()
            result["locked_for"] = duration
        return result

    def record_success(self, username: str, client: str = "") -> None:
        """Clear the counter for an account that just authenticated."""
        self._entries.pop(self._key(username, client), None)

    def reset(self) -> None:
        """Drop all state (tests and operator recovery)."""
        self._entries.clear()

    def tracked_keys(self) -> int:
        return len(self._entries)


GUARD = LoginGuard()


def check_login(username: str, client: str = "") -> tuple[bool, int]:
    return GUARD.check(username, client)


def record_login_failure(username: str, client: str = "") -> dict:
    return GUARD.record_failure(username, client)


def record_login_success(username: str, client: str = "") -> None:
    GUARD.record_success(username, client)
