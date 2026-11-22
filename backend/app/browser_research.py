"""Read-only, allowlisted web research for MARKET-MIND-AI agents.

This is the safe read-only subset of an agent browser: it retrieves a public
web page as plain text. It does not execute JavaScript, follow redirects,
submit forms, click links, download files, use credentials, or touch local
files. It is intended for evidence-gathering in research workflows only.

Security design: docs/BROWSER-RESEARCH-SECURITY.md
"""
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = frozenset({
    "en.wikipedia.org",
    "arxiv.org",
    "export.arxiv.org",
    "www.sec.gov",
    "data.sec.gov",
    "stooq.com",
    "stooq.pl",
    "finance.yahoo.com",
    "query1.finance.yahoo.com",
    "api.coingecko.com",
    "www.coingecko.com",
})

MAX_URL_CHARS = 2_000
MAX_RESPONSE_BYTES = 512_000
MAX_TEXT_CHARS = 30_000
TIMEOUT_SECONDS = 10
USER_AGENT = "MARKET-MIND-AI-ResearchBot/1.0 (read-only research)"
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")


class URLPolicyError(ValueError):
    """Raised when a URL or resolved endpoint violates the read-only policy."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise URLPolicyError("redirects_are_blocked")


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "iframe", "form", "button"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self._SKIP:
            self._skip_depth += 1
        elif tag.lower() in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def validate_url(url: str) -> tuple[str, str]:
    """Return (normalized_url, host) or raise URLPolicyError."""
    if not isinstance(url, str) or not url.strip():
        raise URLPolicyError("url_required")
    url = url.strip()
    if len(url) > MAX_URL_CHARS:
        raise URLPolicyError("url_too_long")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise URLPolicyError("https_required")
    if parsed.username or parsed.password:
        raise URLPolicyError("credentials_in_url_blocked")
    if parsed.port not in (None, 443):
        raise URLPolicyError("nonstandard_port_blocked")
    host = (parsed.hostname or "").lower()
    if not host or host not in ALLOWED_HOSTS:
        raise URLPolicyError("host_not_allowlisted")
    normalized = urlunparse((parsed.scheme, host, parsed.path or "/", "", "", ""))
    return normalized, host


def assert_public_endpoint(host: str) -> None:
    """Block private, loopback, link-local, metadata and other non-global IPs."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLPolicyError("dns_resolution_failed") from exc
    if not infos:
        raise URLPolicyError("dns_resolution_failed")
    for info in infos:
        address = info[4][0]
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise URLPolicyError("private_or_special_address_blocked")


def html_to_text(payload: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(payload)
    return extractor.text()


def fetch_research_page(url: str) -> dict:
    """Fetch one allowlisted public page and return plain text with audit metadata."""
    try:
        normalized, host = validate_url(url)
        assert_public_endpoint(host)
    except URLPolicyError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "url": url if isinstance(url, str) else None,
            "side_effects": False,
            "research_only": True,
        }

    opener = build_opener(_NoRedirect)
    request = Request(
        normalized,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200) or 200)
            headers = Message()
            for key, value in response.headers.items():
                headers[key] = value
            content_type = (headers.get_content_type() or "").lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                return {
                    "ok": False,
                    "error": "unsupported_content_type",
                    "content_type": content_type,
                    "url": normalized,
                    "side_effects": False,
                    "research_only": True,
                }
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        return {
            "ok": False,
            "error": "http_error",
            "status_code": int(exc.code),
            "url": normalized,
            "side_effects": False,
            "research_only": True,
        }
    except (URLError, OSError, TimeoutError) as exc:
        return {
            "ok": False,
            "error": "fetch_failed",
            "detail": type(exc).__name__,
            "url": normalized,
            "side_effects": False,
            "research_only": True,
        }

    response_truncated = len(raw) > MAX_RESPONSE_BYTES
    payload = raw[:MAX_RESPONSE_BYTES]
    charset = headers.get_content_charset() or "utf-8"
    try:
        decoded = payload.decode(charset, errors="replace")
    except LookupError:
        decoded = payload.decode("utf-8", errors="replace")

    text = decoded if content_type == "text/plain" else html_to_text(decoded)
    text_truncated = len(text) > MAX_TEXT_CHARS
    if text_truncated:
        text = text[:MAX_TEXT_CHARS]

    return {
        "ok": True,
        "url": normalized,
        "host": host,
        "status_code": status,
        "content_type": content_type,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "bytes_read": len(payload),
        "response_truncated": response_truncated,
        "text_truncated": text_truncated,
        "javascript_executed": False,
        "redirects_followed": False,
        "downloads": False,
        "credentials_used": False,
        "local_file_access": False,
        "side_effects": False,
        "research_only": True,
        "policy": {
            "https_only": True,
            "allowlisted_hosts": sorted(ALLOWED_HOSTS),
            "private_network_blocked": True,
            "redirects_blocked": True,
        },
    }
