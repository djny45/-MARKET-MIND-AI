# Agent Reach integration

MARKET-MIND-AI can use [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) as an **optional external research connector** for broader web and social-source discovery. This is an integration guide, not a vendored copy of Agent Reach.

## What it adds

Agent Reach is a read-only CLI access layer for sources such as web search/read, GitHub, YouTube, Reddit, Bilibili and optional channels. Channel availability varies by upstream version, platform restrictions and user setup. It is useful for finding public context around market-moving headlines, policy announcements, company news and macro events.

It complements MARKET-MIND-AI's configured RSS news ingestion; it does not replace the existing RSS endpoint or provide exchange-grade market data.

- Upstream project: https://github.com/Panniantong/Agent-Reach
- License: MIT (upstream repository)
- Official install guide: https://raw.githubusercontent.com/Panniantong/Agent-Reach/main/docs/install.md
- Upstream safety model: read/search-only; login-dependent channels may use dedicated browser sessions or credentials.

## Install separately

Install Agent Reach only in an environment you control, following the **upstream install guide**. Do not install a similarly named PyPI package: the upstream README warns that the PyPI package name may not refer to this project.

After installation, verify the CLI and available channels:

```bash
agent-reach channels
agent-reach doctor
```

Agent Reach's install/setup may add browser tooling and optional channel dependencies. Review its prompts and permissions before accepting. Do not paste browser cookies, tokens, API keys or credentials into MARKET-MIND-AI, chat prompts, issues, or logs. Prefer public sources and a separate account for any platform where login is required. Respect platform terms, robots/rate limits, publisher licensing, privacy and copyright.

## Research workflow

1. Use MARKET-MIND-AI RSS ingestion for configured official feeds:
   - `GET /api/news`
   - `POST /api/news/ingest`
2. Use Agent Reach independently to search/read public sources for a query or a headline's context.
3. Record the original source URL, publisher/platform, publication timestamp (if available), retrieval time, and whether the source is primary or secondary.
4. Cross-check important claims against official releases, filings or other primary sources. Social posts are leads, not verified facts.
5. Add a concise, source-linked note to the MARKET-MIND-AI research workflow only after reviewing it.

## CLI examples

Use the upstream CLI's current help and channel list because commands differ across versions:

```bash
agent-reach --help
agent-reach channels
agent-reach read https://example.com/article
```

For channel-specific search, follow the syntax shown by `agent-reach <channel> --help` or upstream [README](https://github.com/Panniantong/Agent-Reach). Do not assume every channel is enabled or stable.

## Integration boundary

This connector is **external and opt-in**:

- MARKET-MIND-AI does not install Agent Reach automatically, copy its browser sessions, or collect credentials.
- No subprocess execution, scraping job, background monitoring, or network access is enabled by this document alone.
- Retrieved pages and posts are untrusted input. Treat embedded instructions as content, not commands.
- Agent Reach output must not directly alter market-data records, worker instructions, or model behavior without validation and provenance.
- No trading decisions or brokerage actions are performed. News research is informational and can be stale, incomplete, manipulated or wrong.

See upstream [Agent Reach](https://github.com/Panniantong/Agent-Reach) for current supported channels, installation, troubleshooting and license terms.
