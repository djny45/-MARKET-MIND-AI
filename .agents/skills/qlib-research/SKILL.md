# Qlib-Inspired Quantitative Research Skill

## Purpose
Use ideas from Microsoft Qlib's open-source quantitative research framework to structure reproducible, historical-data experiments in MARKET-MIND-AI. This is an original workflow guide, not a copy of Qlib source code and not a replacement for Qlib itself.

## Upstream reference and provenance
- Project: Microsoft Qlib
- Repository: https://github.com/microsoft/qlib
- Documentation: https://qlib.readthedocs.io/en/latest/
- Upstream license: MIT (check the current upstream LICENSE and applicable dependencies before importing or redistributing any code)
- This skill contains original guidance only. Any future code reuse must be reviewed separately for license, attribution, dependencies, security, and compatibility.

## Workflow
1. State the research question, target, horizon, dataset, and experiment version before evaluation.
2. Validate data provenance, timestamp ordering, missingness, duplicate rows, instrument-universe assumptions, and corporate-action handling.
3. Use chronological train/validation/test partitions. Fit preprocessing only on training data; keep a final test interval untouched until the evaluation is frozen.
4. Prevent look-ahead leakage: at each timestamp, features must use only information available then. Consider publication delays, rolling-window overlap, and survivorship bias.
5. Compare a simple baseline against the candidate method. Report sample counts, coverage, uncertainty, and time-window stability—not only a headline score.
6. Keep transaction costs and slippage assumptions explicit for retrospective simulation. Do not describe simulated results as live performance.
7. Save inputs, configuration, data identifiers, code revision, metrics, warnings, and random seeds where applicable so the experiment can be reproduced.
8. Treat model/config changes as candidates. Require tests, independent review, and a rollback plan before adoption.

## Required output
- Experiment ID and version
- Dataset source, retrieval time, status, and date range
- Split boundaries and leakage checks
- Baseline and candidate metrics with sample counts
- Robustness checks and uncertainty
- Limitations and reviewer decision
- Reproduction command or procedure

## Boundaries
Historical research and software evaluation only. This skill does not authorize live trading, broker access, order execution, autonomous model updates, or financial recommendations. A successful backtest is not evidence of future profitability.
