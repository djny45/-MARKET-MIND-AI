"""Strict parsing for browser CORS origin allowlists."""
import ipaddress
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
        if any(character.isspace() for character in value):
            raise ValueError("FRONTEND_ORIGINS entries must not contain whitespace")
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
            or parsed.netloc.endswith(":")
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

        # Restrict configured hostnames to ASCII (including explicit Punycode).
        # Python's built-in IDNA codec uses IDNA2003, which can map Unicode
        # labels differently from browser Origin serialization (for example ß).
        if not hostname.isascii():
            raise ValueError("FRONTEND_ORIGINS hostnames must use ASCII or Punycode")
        # Browser Origin serialization omits default ports. Normalize those too,
        # otherwise an allowlist entry ending in :443/:80 will never match.
        if ":" in hostname:
            # Browsers serialize IPv6 origins using the compressed literal form.
            try:
                host = f"[{ipaddress.IPv6Address(hostname).compressed}]"
            except ipaddress.AddressValueError as exc:
                raise ValueError("FRONTEND_ORIGINS contains an invalid IPv6 hostname") from exc
        else:
            try:
                host = hostname.encode("idna").decode("ascii").lower()
            except UnicodeError as exc:
                raise ValueError("FRONTEND_ORIGINS contains an invalid hostname") from exc
        default_port = 80 if parsed.scheme.lower() == "http" else 443
        port_suffix = f":{port}" if port is not None and port != default_port else ""
        normalized = f"{parsed.scheme.lower()}://{host}{port_suffix}"
        if normalized not in origins:
            origins.append(normalized)
    return origins
