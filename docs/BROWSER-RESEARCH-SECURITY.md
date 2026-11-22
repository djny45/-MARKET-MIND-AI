# Read-only browser research — security design

Status: **separate security design and explicit authorization** for adding a
network tool to the read-only MCP server, as required by the root `AGENTS.md`.

Authorization scope: read-only research browsing for the 550 analytical agent
profiles. The capability is exposed as a single MCP tool,
`browser_research_read(url)`, and as the Python helper
`backend/app/browser_research.py`.

## What is allowed

- One HTTPS GET per call to a public host on a fixed allowlist.
- Plain-text (or plain HTML converted to text) response body.
- Result returned to the caller with provenance and audit metadata.

Default allowlist (`browser_research.ALLOWED_HOSTS`): Wikipedia (en), arXiv,
SEC EDGAR (www/data), Stooq, Yahoo Finance (finance/query1), CoinGecko
(api/www). It is code-defined, not user-extensible at runtime.

## Threat model and controls

| Threat | Control |
| --- | --- |
| SSRF to localhost/private networks/metadata | DNS resolution checked with `assert_public_endpoint`; every resolved IP must be `is_global`. Private, loopback, link-local (incl. 169.254.169.254), reserved and IPv6 ULA are rejected. |
| Redirect to a disallowed host | Redirects are disabled (`_NoRedirect` handler raises `URLPolicyError`). No `Location` is followed. |
| Credential or secret disclosure | URLs with userinfo are rejected; no cookies, tokens or auth headers are sent; error details contain only exception class names. |
| Interactive abuse (clicks, forms, downloads, JS) | No browser engine is driven: no JavaScript, no form submission, no link following, no downloads, no local file access. Method is fixed to GET. |
| Non-allowlisted destinations | Exact hostname match against the allowlist; non-standard ports rejected; HTTP rejected. |
| Resource exhaustion | 10-second timeout, 512 KB response cap, 30,000-character text cap, 2,000-character URL cap. |
| Malformed or binary content | Content type limited to HTML/plain text/XHTML; decoding uses declared charset with safe fallback; script/style/iframe/form content is stripped. |
| Untrusted content influencing agents | Returned text is explicitly labelled research data; agents must treat it as untrusted input, never instructions. |

## Scope boundaries

- **Not** a full Browser Use / Playwright driver. It is the deterministic,
  read-only subset needed for evidence gathering; it executes no JavaScript and
  makes no decisions on behalf of an agent.
- No repository or filesystem writes, no database changes, no workflow import or
  execution, no brokerage access, no market-data provider credentials.
- No per-user keys, no state carried between calls, no persistent cookies.

## Audit metadata

Each response includes `retrieved_at` (UTC), normalized URL, host, status, byte
and text counts, truncation flags, and explicit booleans for JavaScript,
redirects, downloads, credentials, local file access and side effects. Callers
should persist these records in their own research notes; the tool itself writes
nothing.

## Verification

`backend/tests/test_browser_research.py` covers URL policy, SSRF blocking,
redirect refusal, script stripping, truncation and the no-side-effects contract.
`backend/tests/test_mcp_server.py` verifies the tool is included in the fixed
MCP allowlist and that diagnostics do not claim unrestricted network access.

## Upgrade path

If a full agent browser is later required, it must be a separate design: an
isolated container with no credentials, no local network, explicit domain
allowlisting, JS sandboxing and independent review. Adding Playwright or
`browser-use` to this process would defeat the controls above.
