# News and event sources

The project ingests publisher metadata and links, not full article mirrors.

## Initial configurable RSS examples
- SEC press releases: https://www.sec.gov/news/pressreleases.rss
- ECB press releases: https://www.ecb.europa.eu/rss/press.html
- Federal Reserve press releases: https://www.federalreserve.gov/feeds/press_all.xml

These examples require production verification for availability, user-agent requirements and publisher terms.

## Further candidates
- Relevant central-bank RSS feeds and official statements.
- Government statistical release calendars and APIs.
- Exchange notices, corporate actions and issuer investor-relations feeds.
- Licensed news providers where broad coverage, redistribution or low-latency delivery is needed.

## Required metadata and controls
Publisher, canonical URL, headline, published timestamp, ingestion timestamp, language, entity candidates, classification confidence and content-use policy. Deduplicate URLs, preserve corrections, detect stale feeds, avoid unsupported entity matching and link generated summaries to original sources. Headlines and sentiment are not signals by themselves.


## Public social/community research (experimental adapter)

The research-only adapter is `backend/app/social_sources.py`. It accepts explicitly configured public RSS feeds and returns titles, links, timestamps, source provenance, per-feed errors, and deduplicated IDs. It does not mirror article bodies or scrape authenticated/private pages.

The companion agent skill is `.agents/skills/social-research/SKILL.md`.

### Important coverage limits
- Reddit RSS may be accessible for some public communities, but availability, rate limits, and policies can change.
- X/Twitter, Instagram, TikTok, Telegram, and Discord are **not** covered automatically or guaranteed to be free. API access, credentials, permissions, and platform terms vary.
- This is configured-feed coverage only, not a complete social-media scan.
- User-generated posts are unverified claims. Verify material statements against primary sources; sentiment is descriptive context, never a forecast or trade signal.
- No order execution or financial recommendation is provided.
