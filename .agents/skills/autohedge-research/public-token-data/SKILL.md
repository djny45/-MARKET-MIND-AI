# AutoHedge-derived Public Token Data Research Skill

**Upstream:** [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)  
**Adaptation:** Public metadata/price lookup only; not a transaction tool.  
**Licence:** MIT; see `../NOTICE.md`.

## Purpose
Retrieve explicitly requested public Solana token metadata and public prices for research reports.

## Workflow
1. Search token metadata by an exact symbol, name, or mint identifier.
2. Verify the returned mint identifier and token metadata; symbols alone are not unique.
3. Retrieve public prices only for explicit mint IDs.
4. Record provider, request time, returned timestamp/block information where present, and response coverage.
5. Mark missing prices and provider failures; do not synthesize substitutes.
6. Cross-check suspicious or stale results with another independently sourced feed before relying on them.

## Guardrails
Public metadata and price lookup only. No holdings endpoint, wallet access, private-key handling, transaction construction, signing, order creation, swap submission, or token transfer.
