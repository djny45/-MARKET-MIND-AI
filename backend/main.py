"""Vercel ASGI entrypoint for MARKET-MIND-AI.

The current persistence layer is SQLite-backed and is not yet safe for
serverless deployment. Disable process-startup task recovery here; durable
recovery must be moved to a database-backed scheduled/queue worker before
production traffic is enabled.
"""
import os

os.environ.setdefault("MARKET_MIND_STARTUP_RECOVERY", "false")

from app.main import app  # noqa: E402

__all__ = ["app"]
