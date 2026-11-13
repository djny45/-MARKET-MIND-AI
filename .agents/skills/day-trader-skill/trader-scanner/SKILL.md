---
name: historical-universe-coverage-audit
description: Audit historical instrument-universe coverage, symbol mapping, missing periods, and source metadata.
---
# Historical universe coverage audit

## Purpose
Inspect a supplied list of instruments and historical datasets for coverage and data-quality gaps.

## Procedure
1. Normalize symbols only when an explicit mapping source is provided.
2. Report duplicate identifiers, unmapped symbols, missing intervals, and date-range differences.
3. Distinguish delisted, inactive, unavailable, and unrequested instruments where evidence supports it.
4. Summarize coverage by source, interval, and instrument.
5. Avoid ranking instruments by expected return or suitability.

## Boundaries
Do not screen for securities to buy, rank investment opportunities, generate live alerts, or place orders. Use only authorized public or user-supplied data.
