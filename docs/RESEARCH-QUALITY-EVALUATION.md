# Research draft traceability evaluator

The deterministic evaluator in `backend/app/research_quality_eval.py` checks
basic source-reference structure for a supplied research draft. It is a
traceability diagnostic—not a fact checker, source-authenticity validator,
claim-entailment system, or market-performance score.

## What it reports

- Claim counts and the fraction of claims with at least one source reference.
- The fraction of claims whose references all match IDs in the supplied registry.
- Unknown source IDs and per-claim reference status.
- Duplicate source IDs in the registry after trimming whitespace. Registry
  duplicates are reported separately; they are not silently interpreted as
  additional unique sources.
- A small set of uncertainty/limitation markers present in the draft text.
- Optional deltas against caller-supplied baseline coverage metrics.

## Important interpretation limits

- A matching source ID only means the ID exists in the supplied registry.
- The evaluator does not open sources or check whether they support a claim.
- The uncertainty-marker check is a literal keyword scan, not semantic review.
- Baseline metrics are supplied by the caller and are not independently verified.
- Coverage percentages do not measure truth, reasoning quality, forecast skill,
  or investment value.

## Run tests

From the repository root:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_research_quality_eval -v
```

The tests include duplicate-ID normalization and reporting. Run the command
above to verify the evaluator in your environment.
