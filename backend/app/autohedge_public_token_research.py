"""Public Solana token metadata/price lookups. No wallet or transaction methods."""
from __future__ import annotations

import os
import re
import httpx

BASE_URL = "https://api.jup.ag"
MINT_LIST_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z,]{1,6000}$")


def _headers() -> dict[str, str]:
    key = os.getenv("JUPITER_API_KEY", "").strip()
    return {"x-api-key": key} if key else {}


def _validate_query(value: str, field: str, max_length: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"{field} must be a non-empty string of at most {max_length} characters")
    return value.strip()


def search_public_tokens(query: str, timeout_seconds: float = 10.0) -> list[dict]:
    """Search the public token metadata endpoint with bounded input and timeout."""
    query = _validate_query(query, "query")
    timeout = min(max(float(timeout_seconds), 1.0), 20.0)
    response = httpx.get(
        f"{BASE_URL}/tokens/v2/search",
        params={"query": query},
        headers=_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("unexpected public token-search response shape")
    return [item for item in payload if isinstance(item, dict)]


def get_public_token_prices(mints: str, timeout_seconds: float = 10.0) -> dict:
    """Retrieve public prices for explicitly supplied token mint IDs."""
    mints = _validate_query(mints, "mints", max_length=6000)
    if not MINT_LIST_RE.fullmatch(mints):
        raise ValueError("mints contains unsupported characters")
    mint_list = [item for item in mints.split(",") if item]
    if not 1 <= len(mint_list) <= 100:
        raise ValueError("provide between 1 and 100 comma-separated mint IDs")
    timeout = min(max(float(timeout_seconds), 1.0), 20.0)
    response = httpx.get(
        f"{BASE_URL}/price/v3",
        params={"ids": ",".join(mint_list)},
        headers=_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("unexpected public token-price response shape")
    return payload
