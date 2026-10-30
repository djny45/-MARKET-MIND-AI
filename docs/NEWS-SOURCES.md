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
