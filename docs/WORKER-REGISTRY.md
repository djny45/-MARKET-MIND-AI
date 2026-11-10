# Worker Registry Integrity

The worker registry is a deterministic manifest of **550 analytical worker templates**. It is not a fleet of 550 independently running models. All profiles reference the shared `shared_central_intelligence` core, and registry evaluation does not execute inference or broker actions.

## Validation layers

`evaluate_registry()` checks three separate layers:

1. **Worker profiles** — expected count and ordered IDs, required non-empty fields, allowed department, worker kind, template status, and shared-core identity.
2. **Worker skill references** — every `skill_refs` value must be a string, resolve to an allowlisted catalog ID, be available on disk, and occur only once per worker.
3. **Skill catalog integrity** — the catalog must be a list; each entry must be an object with a non-empty string `id` and a boolean `available` field; IDs must be unique.

Catalog integrity is reported in `skill_catalog_integrity`:

| Field | Meaning |
| --- | --- |
| `catalog_entry_count` | Number of catalog entries received |
| `valid_entry_count` | Entries that satisfy the required shape |
| `malformed_entry_indexes` | Zero-based indexes of entries with an invalid shape |
| `duplicate_skill_ids` | Repeated IDs found in the catalog |

A non-list catalog is normalized to an empty list for safe reporting and adds `skill_catalog_not_a_list` to the errors. Invalid entries and duplicate IDs also make the registry invalid; they are not silently accepted.

## Skill coverage is not semantic alignment

The department/domain matrix reports which catalog domains are represented by assigned research skill IDs. It is explicitly labeled `catalog_domain_coverage_only_not_semantic_alignment`. It does not prove that a skill is appropriate for a worker's department or specialty.

The `specialty_skill_alignment` result remains `not_evaluated` until a curated mapping has documented rationale and review evidence. Do not infer semantic fit from a valid ID, a file being present, or a non-zero coverage count.

## Safety and execution boundary

Worker profiles are templates and skill references are guidance links. The registry is not an execution engine. The current boundary remains:

- no independent model per worker;
- no autonomous model updates or self-promotion;
- no broker or order execution;
- no claim of live market coverage from catalog validation.

## Tests

Run the backend unit suite from the repository root:

```bash
python -m unittest discover -s backend/tests -v
```

The worker registry tests cover valid manifests, malformed profiles, invalid and duplicate worker skill references, unavailable skills, malformed catalog entries, duplicate catalog IDs, and explicit non-alignment claims.
