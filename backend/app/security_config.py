"""Strict parsing for browser CORS origin allowlists."""
from urllib.parse import urlsplit


def parse_frontend_origins(raw: str) -> list[str]:
    """Parse explicit HTTP(S) origins; reject wildcard and URL paths or credentials."""
    if not isinstance(raw, str):
        raise ValueError("FRONTEND_ORIGINS must be a comma-separated string")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        raise ValueError("FRONTEND_ORIGINS must contain at least one explicit origin")

    origins: list[str] = []
    for value in values:
        if value == "*" or "*" in value:
            raise ValueError("FRONTEND_ORIGINS does not permit wildcard origins")
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            # Accessing .port also validates malformed port syntax and range.
            port = parsed.port
        except ValueError as exc:
            raise ValueError("FRONTEND_ORIGINS contains a malformed origin") from exc

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "FRONTEND_ORIGINS entries must be HTTP(S) origins without paths, "
                "credentials, queries, or fragments"
            )

        # Normalize scheme/host casing and the optional root slash while preserving
        # IPv6 brackets and an explicitly configured port.
        host = parsed.netloc.rsplit("@", 1)[-1]
        normalized = f"{parsed.scheme.lower()}://{host.lower()}"
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        if normalized not in origins:
            origins.append(normalized)
    return origins
