# Local-only research tooling

The following upstream projects are vendored **locally only** under
`third_party/` (excluded via `.git/info/exclude`, not committed, not pushed).
They are reference material for the 550 analytical agent profiles: none is
installed as a service, executed automatically, or integrated with brokerage.

| Directory | Upstream | Commit | License | Purpose |
| --- | --- | --- | --- | --- |
| `third_party/FinceptTerminal/` | `Fincept-Corporation/FinceptTerminal` | `914134de5fd227fe66969c4591ac9ca7e461cdf4` | AGPL-3.0 | Open-source Qt financial terminal reference (97 MB) |
| `third_party/camofox-browser/` | `jo-inc/camofox-browser` | `31376c27db94204ffdc635ae71a7f61328e91a5e` | MIT | Full agent browser; **the only one actually integrated** via MCP (see `docs/CAMOFOX-BROWSER-SECURITY.md`) |
| `third_party/freqtrade/` | `freqtrade/freqtrade` | `a025e7fb3b3acf0e90fd86a9f597aea5b528e1b7` | GPL-3.0 | Crypto trading-strategy and backtesting reference (37 MB) |

## Why these are not committed

AGPL-3.0 and GPL-3.0 are strong copyleft licenses; this repository is MIT.
Copying their source into the repo would create license-compliance obligations
and conflict with the MIT license. Keeping them in an excluded local directory
preserves provenance for research without redistributing the source.

## How agents use them

- **Freqtrade methodology:** the allowlisted skill `freqtrade-backtest-research`
  provides an original, research-only summary of its validation concepts
  (lookahead checks, recursive-indicator stability, fees, walk-forward tuning,
  reproducibility). No upstream code is imported or executed.
- **Camofox browser:** registered as a separate MCP server, with the security
  design in `docs/CAMOFOX-BROWSER-SECURITY.md`. Start the REST server with
  `bash scripts/setup_camofox_browser.sh` (requires Node.js 22+).
- **FinceptTerminal / Freqtrade source:** read-only study material. No live
  trading, exchange keys, order routing or broker connections are configured.

## Refreshing a local copy

Each directory can be re-cloned from its upstream URL at the pinned commit.
Do not remove the `.git/info/exclude` entries: without them a 130+ MB of
third-party source could be committed accidentally.
