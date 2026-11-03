---
name: social-research
description: Research public social discussion using approved public feeds and source links. Use for topic research, not trading predictions or recommendations.
---

# Social Research Skill

## Purpose
Summarize public social/community discussion as research context. Do not place orders, recommend buying or selling, or treat sentiment as a forecast.

## Supported approach
- Use explicitly configured public RSS feeds (including Reddit RSS where accessible).
- The existing news service handles publisher and official RSS sources.
- X/Twitter, Instagram, TikTok, Telegram, and Discord are not guaranteed free or universally accessible. APIs, authentication, permissions, and terms may limit access. Integrate only approved adapters.
- Never bypass logins, paywalls, access controls, private communities, rate limits, or platform terms.

## Workflow
1. Define topic/entities and time window.
2. Fetch only approved public feeds.
3. Preserve source URL, publisher/community, publication and retrieval timestamps.
4. Deduplicate by stable ID or canonical URL.
5. Report unavailable sources, errors, stale data, and sample size. Never claim comprehensive platform coverage.
6. Summarize themes and disagreement with source links. Clearly label user-generated claims as unverified.
7. Sentiment is descriptive and noisy—not a price forecast, trading signal, or setup.

## Output
- Topic and time window
- Sources checked and unavailable
- Representative themes with links and timestamps
- Conflicting claims and verification needs
- Coverage caveats

## Safety
Research and education only. No financial advice, personalized trading recommendations, execution, or automated action based on social posts.
