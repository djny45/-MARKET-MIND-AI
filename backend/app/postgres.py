"""PostgreSQL connectivity boundary for serverless deployment.

This module is additive: existing stores remain SQLite-backed until each
store has an explicit schema migration and parity tests. A successful probe
does not imply that application persistence has migrated.
"""
from __future__ import annotations

import os
from typing import Any


def database_url(environ: dict[str, str] | None = None) -> str | None:
    """Return the configured DSN without logging or exposing it."""
    env = os.environ if environ is None else environ
    value = env.get("DATABASE_URL", "").strip()
    return value or None


def postgres_readiness(
    environ: dict[str, str] | None = None,
    *,
    connect: Any = None,
) -> dict[str, Any]:
    """Probe PostgreSQL with a short timeout; never return DSN or exception text."""
    dsn = database_url(environ)
    if not dsn:
        return {
            "status": "not_configured",
            "configured": False,
            "reachable": False,
            "driver": "psycopg",
        }

    try:
        if connect is None:
            import psycopg
            connect = psycopg.connect

        with connect(dsn, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if not row or row[0] != 1:
                    raise RuntimeError("database_probe_failed")
        return {
            "status": "ready",
            "configured": True,
            "reachable": True,
            "driver": "psycopg",
        }
    except Exception as exc:  # redact driver/network details
        return {
            "status": "not_ready",
            "configured": True,
            "reachable": False,
            "driver": "psycopg",
            "error_type": type(exc).__name__,
        }


__all__ = ["database_url", "postgres_readiness"]
