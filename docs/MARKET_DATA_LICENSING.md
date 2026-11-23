# Market-data licensing and legal review (2026-11-23)

Status: **review of code and configuration only; no legal approval is claimed.**

## Verified implementation facts

- `backend/app/data_licensing_gate.py` blocks unauthorized providers; no
  licensed live/delayed provider is configured.
- `GET /api/providers/status` reports `no_live_provider_configured` and lists
  only the synthetic fixture adapter as available.
- `backend/app/market_data.py` distinguishes `live`, `delayed`, `historical`
  and `synthetic`; the sample endpoint returns a labelled synthetic batch.
- Yahoo/Stooq historical adapters are best-effort research helpers and attach
  warnings that the data is not real-time or execution-grade. Their redistribution
  and API terms are **not** verified by this repository.
- `POST /api/market-data/store` now rejects live/delayed claims unless the
  source is listed in `MARKET_MIND_ATTESTED_DATA_SOURCES`, which is empty by
  default.

## Unresolved legal requirements (operator action)

1. Identify the exact provider and data product intended for use.
2. Obtain and archive the provider's license/terms, including redistribution,
   caching, delay and attribution clauses.
3. Record written legal approval with date and approver before enabling any
   live or delayed source.
4. Configure `MARKET_MIND_ATTESTED_DATA_SOURCES` with only approved source IDs;
   place credentials in a 0600 environment file, never in code or logs.
5. Verify `GET /api/providers/status` afterwards and archive the response as
   evidence.

No credentials, license approvals or market prices have been invented. The
platform must not display live/delayed labels until steps 1–5 are completed.
