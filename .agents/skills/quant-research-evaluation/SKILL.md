# Quant Research Evaluation Skill

## Purpose
Help MARKET-MIND-AI produce reproducible, evidence-aware evaluations of historical market datasets and deterministic research components. This playbook is for software quality and research methodology—not investment advice, price forecasts, trading signals, or order execution.

## Workflow
1. **Confirm the data contract first.** Require normalized OHLCV rows with timezone-aware timestamps, a declared source/status, retrieval timestamp, unique ascending timestamps, and explicit missing-data diagnostics. Treat synthetic fixtures as tests only.
2. **Define the evaluation question before looking at results.** Record the component/version, inputs, expected outputs, metrics, and acceptance threshold. Avoid changing criteria after observing results.
3. **Use chronological separation.** Never randomly shuffle time-series rows across train/validation/test. If model research is enabled elsewhere, fit preprocessing and feature selection only on the training window; keep validation for selection and test for final evaluation. Apply an embargo/gap where labels or rolling windows overlap.
4. **Guard against leakage.** Features at time t may use only information available at or before t. Verify rolling-window alignment, publication/retrieval delays, survivorship and universe-selection assumptions, and target construction. Include a deliberately shifted/leaky fixture to ensure the checker catches forbidden future information.
5. **Evaluate robustness, not a single score.** Report coverage, sample count, missingness, stability across time windows, sensitivity to fees/slippage assumptions if relevant to a retrospective simulation, and confidence/uncertainty. Separate descriptive statistics from model claims.
6. **Keep provenance attached.** Every report should include dataset/source identifiers, data status, date range, retrieval time, schema/version, code or component version, parameters, and warnings. Never present synthetic or unverified data as real observations.
7. **Use deterministic regression tests.** Include normal, empty, malformed, duplicate, out-of-order, timezone-naive, stale, and future-dated inputs. Pin small fixtures; avoid network calls in unit tests.
8. **Promote changes only through governance.** A candidate worker/model configuration remains a proposal until independent review, regression tests, reproducibility checks, and a rollback plan are recorded. Do not auto-apply updates or claim autonomous self-training.

## Suggested evaluation report
- Evaluation ID and timestamp
- Component and version
- Dataset provenance/status and date range
- Split boundaries and leakage checks
- Metrics with sample counts and missingness
- Baseline comparison and uncertainty
- Known limitations and unresolved bias
- Reviewer decision, test evidence, and rollback reference

## Open-source reference
This methodology is an original project playbook informed by the modular research/evaluation concepts documented by Microsoft Qlib. It does not copy or vendor Qlib code.

- Qlib repository: https://github.com/microsoft/qlib
- Qlib license: MIT (verify the upstream LICENSE before importing code or files)
- Qlib documentation: https://qlib.readthedocs.io/en/latest/

## Safety and scope
Historical analysis and software evaluation only. No broker APIs, order placement, live trading automation, or recommendations to buy/sell assets.
