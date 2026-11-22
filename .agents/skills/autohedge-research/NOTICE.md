# Third-party attribution

This directory contains original MARKET-MIND-AI research-only adaptations of role concepts and prompt structure from:

- Project: [AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)
- Copyright notice in upstream LICENSE: Copyright (c) 2023 Eternal Reclaimer
- Upstream licence: MIT
- Upstream files reviewed: `autohedge/prompts.py`, `autohedge/workers.py`, `autohedge/tools/tools_registry.py`, and `README.md`.

The upstream project includes autonomous trading and transaction-execution functionality. These adaptations intentionally exclude execution instructions, wallet handling, signing, brokerage connectivity, order routing, and live-trading workflows. No upstream historical trade-log CSV files are included.

The MIT licence permits use, modification, distribution, and sublicensing subject to retaining the applicable copyright and permission notice. The upstream licence text is available at the project URL above.


## Additional adapted research component

The market-making research lab is an original implementation inspired by the concepts in upstream `experimental/market_making.py`; it does not copy its continuous strategy loop, venue polling, network fallback, or order placement flow. The upstream source licence and copyright notice above also cover attribution for this adaptation.

## Additional source adaptations

- `backend/app/autohedge_market_making_research.py` is an original, pure-calculation adaptation informed by upstream `experimental/market_making.py`. It excludes continuous venue polling, order placement, background execution loops, and persistent order logs.
- `backend/app/autohedge_public_token_research.py` is an original read-only adapter informed by upstream `autohedge/tools/jupiter_price.py` and `autohedge/tools/jupiter_search.py`. It excludes holdings lookup, wallet-derived identity, order construction, and signing.
