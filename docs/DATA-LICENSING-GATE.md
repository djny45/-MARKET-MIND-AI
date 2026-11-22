# Licensed data sources — access gate

`backend/app/data_licensing_gate.py` is the first layer of a hypothetical
licensed live integration. It requires explicit source authorization and manual
licensing review. It does not itself connect to providers.

## Rules

- Sources are blocked unless authorized.
- Sources requiring license review (e.g. Alpha Vantage) are pending until
  `license_review_completed` is set.
- Known-unauthorized sources (`yahoo-finance-chart`, `stooq`,
  `free-web-scrapers`) are always blocked.
- No credentials are stored; consumers must use their own, separately reviewed
  secrets.

## Usage

```python
from app.data_licensing_gate import DataLicensingGate

gate = DataLicensingGate(license_review_completed=True)
gate.validate("alpha-advantage")
gate.manifest()  # summary of authorized / pending / blocked sources
```

Covered by 5 tests in `backend/tests/test_data_licensing_gate.py`.
