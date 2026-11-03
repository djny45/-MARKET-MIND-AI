"""Research-only public RSS ingestion for configured social/community sources.

Only use feeds the operator is permitted to access. RSS availability and platform
policies change; this adapter does not scrape authenticated/private pages.
"""
import asyncio
import hashlib
import time
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from xml.etree import ElementTree as ET


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so an allowlisted feed cannot redirect to an arbitrary host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("RSS redirects are not followed")


def _source_record(item: dict, channel: str) -> dict:
    """Normalize news/social items into a shared, provenance-preserving schema."""
    url = (item.get("url") or item.get("link") or "").strip()
    title = (item.get("title") or "").strip()
    source = (item.get("source") or item.get("publisher") or "unknown").strip()
    published = item.get("published_at") or item.get("published")
    retrieved = item.get("retrieved_at") or item.get("ingested_at")
    record_id = item.get("id") or hashlib.sha256(
        f"{channel}|{source}|{url}|{title}".encode()
    ).hexdigest()
    return {
        "id": record_id,
        "channel": channel,
        "source": source,
        "url": url,
        "title": title,
        "published_at": published,
        "retrieved_at": retrieved,
        "claim_status": "unverified",
        "content_policy": item.get("content_policy", "metadata_only"),
    }


def merge_research_evidence(news_items: list[dict], social_items: list[dict]) -> dict:
    """Merge feed metadata into one stable, provenance-preserving evidence list."""
    records = [
        _source_record(item, "news") for item in news_items
    ] + [
        _source_record(item, "social") for item in social_items
    ]
    # Deduplicate only identical source URLs; retain channel and original source.
    seen = set()
    merged = []
    for record in records:
        key = (record["source"].casefold(), record["url"].casefold())
        if record["url"] and key in seen:
            continue
        if record["url"]:
            seen.add(key)
        merged.append(record)
    merged.sort(
        key=lambda record: str(record.get("published_at") or ""),
        reverse=True,
    )
    return {
        "schema": "market_mind_evidence_v1",
        "items": merged,
        "count": len(merged),
        "channels": sorted({record["channel"] for record in merged}),
        "claim_status": "unverified_until_cross_checked",
        "coverage": "only_configured_sources",
    }


def parse_rss(raw: bytes, source: str, feed_url: str) -> list[dict]:
    root = ET.fromstring(raw)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        date = (item.findtext("pubDate") or "").strip()
        try:
            published = parsedate_to_datetime(date).isoformat() if date else None
        except (TypeError, ValueError, OverflowError):
            published = None
        item_id = hashlib.sha256(f"{source}|{link}".encode()).hexdigest()
        items.append({
            "id": item_id, "source": source, "feed_url": feed_url,
            "title": title, "url": link, "published_at": published,
            "retrieved_at": time.time(),
            "content_policy": "title_link_metadata_only",
        })
    return items


async def fetch_public_rss(source: str, feed_url: str, timeout: int = 8) -> dict:
    """Fetch one configured public RSS feed; failures are returned as status."""
    def fetch():
        req = Request(feed_url, headers={
            "User-Agent": "MARKET-MIND-AI public social research"
        })
        opener = build_opener(_NoRedirectHandler())
        with opener.open(req, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            return parse_rss(response.read(1_500_000), source, feed_url)

    try:
        items = await asyncio.to_thread(fetch)
        return {"source": source, "feed_url": feed_url, "status": "ok",
                "count": len(items), "items": items}
    except Exception as exc:
        return {"source": source, "feed_url": feed_url, "status": "error",
                "count": 0, "items": [], "error": str(exc)}


async def ingest_public_social_feeds(feeds: dict[str, str],
                                     concurrency: int = 3) -> dict:
    """Fetch configured feeds only; no claim of platform-wide coverage."""
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 8)))

    async def run(name: str, url: str):
        async with semaphore:
            return await fetch_public_rss(name, url)

    results = await asyncio.gather(*(run(name, url)
                                    for name, url in feeds.items()))
    unique = {item["id"]: item for result in results
              for item in result["items"]}
    return {
        "items": list(unique.values()),
        "sources_checked": len(feeds),
        "sources_ok": sum(result["status"] == "ok" for result in results),
        "source_results": results,
        "coverage": "configured_public_feeds_only",
        "execution": "disabled",
        "note": "Posts are unverified claims; sentiment is not a forecast or trade signal.",
    }
