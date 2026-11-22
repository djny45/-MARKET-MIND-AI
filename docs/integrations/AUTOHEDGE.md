# AutoHedge integration record

**Upstream:** https://github.com/The-Swarm-Corporation/AutoHedge  
**Reviewed default branch:** `main`  
**Upstream licence:** MIT  
**Integration target:** draft release-candidate PR #48

## Imported

The `.agents/skills/autohedge-research/` directory contains five original research-only adaptations of the upstream agent-role concepts:

- Director coordination and evidence synthesis
- Quantitative analysis and reproducible evaluation
- News and public-sentiment research
- Risk assessment
- Independent thesis validation, replacing the upstream execution-agent role

The skills are registered in `backend/app/skill_catalog.py` and assigned through `backend/app/workers.py`. The common Director coordination skill is attached to every one of the 550 specialist profiles. Other skills are assigned by department. The profiles continue to share the configured inference core; this does not instantiate 550 separate foundation models.

The upstream MIT attribution and source provenance are recorded in `.agents/skills/autohedge-research/NOTICE.md`.

## Explicitly not imported

### Wallet key handling and signing

The upstream `autohedge/tools/ultra_tools.py` reads `SOLANA_PRIVATE_KEY` from the environment, constructs a Solana keypair, signs a versioned transaction, and posts the signed payload to Jupiter's `/execute` endpoint. This wallet/signing/execution path is excluded and must not be connected to MARKET-MIND-AI's worker runtime.

### Autonomous order execution

The upstream tool registry exposes `execute_trade` and `get_order`. Those functions, execution-agent prompts, wallet configuration, and autonomous order routing are excluded. MARKET-MIND-AI remains a research system with no brokerage connectivity, order routing, wallet signing, or live-trading activation.

### Experimental market making

Upstream `experimental/market_making.py` contains a continuous strategy loop, but the shown order method is named `simulate_order` and changes an in-memory inventory. Its market-data logic can fall back to hard-coded synthetic prices; the file is not a verified live exchange execution adapter. It is not copied into the application runtime. The quant/risk research skills capture the transferable analysis concepts without importing this loop.

### Historical trade logs

The upstream tree contains:

| Upstream file | Size |
|---|---:|
| `logs/trades_20250305_193100.csv` | 30,294,201 bytes |
| `logs/trades_20250305_193129.csv` | 6,855,831 bytes |

The connector could not retrieve the contents for schema, provenance, sensitive-field, and data-quality review. These files are therefore not copied into this repository. A public upstream file is not automatically a validated dataset suitable for model ingestion. Reconsider only after content and provenance validation; do not place secrets or personal data in training/research fixtures.

## Verification

The skill catalogue unit test covers the five additional entries and their research-only mode. Full GitHub Actions status must be checked against the latest branch HEAD before treating this integration as verified.
