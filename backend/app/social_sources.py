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
    """Normalize metadata and attach explainable provenance-quality flags."""
    url = (item.get("url") or item.get("link") or "").strip()
    title = (item.get("title") or "").strip()
    source = (item.get("source") or item.get("publisher") or "unknown").strip()
    published = item.get("published_at") or item.get("published")
    retrieved = item.get("retrieved_at") or item.get("ingested_at")
    record_id = item.get("id") or hashlib.sha256(
        f"{channel}|{source}|{url}|{title}".encode()
    ).hexdigest()
    missing = []
    if not source or source.casefold() == "unknown":
        missing.append("source_name_missing")
    if not url:
        missing.append("source_url_missing")
    if not title:
        missing.append("title_missing")
    if not published:
        missing.append("publication_time_missing")
    return {
        "id": record_id,
        "channel": channel,
        "source": source,
        "url": url,
        "title": title,
        "published_at": published,
        "retrieved_at": retrieved,
        "claim_status": "unverified",
        "provenance_quality": "incomplete" if missing else "metadata_complete",
        "provenance_gaps": missing,
        "content_policy": item.get("content_policy", "metadata_only"),
    }


def merge_research_evidence(news_items: list[dict], social_items: list[dict]) -> dict:
    """Merge feed metadata and produce cautious, explainable review signals."""
    records = [
        _source_record(item, "news") for item in news_items
    ] + [
        _source_record(item, "social") for item in social_items
    ]
    seen = set()
    merged = []
    for record in records:
        key = (record["source"].casefold(), record["url"].casefold())
        if record["url"] and key in seen:
            continue
        if record["url"]:
            seen.add(key)
        merged.append(record)

    # Identical normalized titles across channels are review candidates only.
    # This does not establish that the underlying claims agree or are true.
    title_groups = {}
    for record in merged:
        normalized_title = " ".join(record["title"].casefold().split())
        if normalized_title:
            title_groups.setdefault(normalized_title, []).append(record)
    corroboration_candidates = []
    for title, group in title_groups.items():
        channels = sorted({record["channel"] for record in group})
        if len(channels) > 1:
            corroboration_candidates.append({
                "normalized_title": title,
                "channels": channels,
                "source_urls": sorted({record["url"] for record in group if record["url"]}),
                "review_status": "manual_cross_check_required",
                "note": "Matching titles are not proof of independent corroboration or agreement.",
            })

    merged.sort(
        key=lambda record: str(record.get("published_at") or ""),
        reverse=True,
    )
    counts = {
        "news": sum(record["channel"] == "news" for record in merged),
        "social": sum(record["channel"] == "social" for record in merged),
    }
    return {
        "schema": "market_mind_evidence_v1",
        "items": merged,
        "count": len(merged),
        "channels": sorted({record["channel"] for record in merged}),
        "channel_counts": counts,
        "provenance_complete_count": sum(
            record["provenance_quality"] == "metadata_complete" for record in merged
        ),
        "provenance_incomplete_count": sum(
            record["provenance_quality"] == "incomplete" for record in merged
        ),
        "corroboration_candidates": corroboration_candidates,
        "claim_status": "unverified_until_cross_checked",
        "coverage": "only_configured_sources",
        "review_note": "Quality flags measure metadata completeness, not publisher credibility or truth.",
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
