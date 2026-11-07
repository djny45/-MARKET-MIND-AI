# Self-Evolving MARKET-MIND-AI: Capability Blueprint

## Target

Evolve MARKET-MIND-AI from a research terminal into a controlled software-research agent that can discover public technical resources, understand their structure, propose adaptations, learn reusable skills, and improve its own code through measured, reviewable changes.

The system remains a **single shared intelligence core**. Worker/profile identities are task-specialized contracts—not separate independently trained models.

## Capability model

| Capability | Intended behavior | Required evidence / gate |
|---|---|---|
| Self-crawling | Discover public GitHub repositories, docs, and web resources relevant to a task | Allowlisted hosts, URL validation, source/commit provenance, bounded fetches, rate limits |
| Self-reverse-engineering | Inspect repository layout, APIs, dependency graph, tests, and architecture without executing unknown code | Static-first analysis, file manifest, threat notes, confidence and evidence references |
| Open-source reuse | Identify useful modules and propose minimal adaptations | License and NOTICE review, attribution, dependency/security review, human approval |
| Self-building | Create isolated patch branches and run tests against a baseline | Restricted sandbox, no credentials, network disabled by default, resource limits |
| Skill learning | Convert repeatable successful procedures into versioned skill proposals | Skill schema validation, source citations, evaluation suite, provenance, review gate |
| Self-adaptation | Adjust tool selection and workflow based on observed task outcomes | Explicit metrics, bounded experiments, regression checks, reversible changes |
| Self-learning | Learn from task feedback and evaluation history | Dataset/version provenance, leakage checks, offline benchmark, no unsupported claims of model training |
| Self-copying | Reuse open-source code or skill patterns where permitted | Never copy blindly; retain license/NOTICE; patch only necessary components |
| Self-recovery | Detect failed updates and return to last known-good version | Atomic promotion, backup, rollback, audit event |

## Current implementation added in this increment

- `backend/app/open_source_intake.py`: canonical GitHub repository URL validation and a structured intake plan.
- `POST /api/open-source/intake`: creates a review checklist for a candidate source.\n- `POST /api/open-source/crawl-metadata`: fetches bounded GitHub repository metadata and pins the default-branch commit SHA.
- Intake currently **does not fetch, clone, execute, copy, install, or merge** third-party code.
- Unknown or merely declared licenses do not authorize reuse.
- Unit and API regression tests cover URL validation and default-deny behavior.

The first metadata-only crawler is now implemented. It is not yet a full repository crawler: it does not enumerate source trees, download source files, inspect dependencies, or adapt code.

## Proposed execution pipeline

1. **Discover** — collect candidate source URLs from a task query.
2. **Normalize** — allowlist domains, canonicalize URLs, reject credentials/redirect tricks and unsupported paths.
3. **Fetch metadata** — retrieve only bounded public metadata and file manifests through a dedicated connector.
4. **Pin source** — record immutable commit SHA, retrieval time, source URL, license/NOTICE text hashes, and file list.
5. **Inspect** — static repository mapping, architecture summary, dependency and script review; never execute unknown setup scripts.
6. **Select** — compare candidate components against an explicit need and compatibility matrix.
7. **Propose** — produce a minimal diff with attribution and licensing notes.
8. **Sandbox** — run tests and static analysis in an isolated environment with no secrets and restricted networking.
9. **Evaluate** — compare before/after benchmark results, regression tests, security findings, and resource costs.
10. **Review** — human approval for dependency additions, skill activation, or code promotion.
11. **Promote** — merge only approved changes; create a signed/auditable change record.
12. **Observe / rollback** — monitor regression signals and revert to the previous known-good snapshot if required.

## Non-negotiable safeguards

- No unrestricted shell, arbitrary binary execution, or credential access by the research agent.
- No unreviewed code from websites or repositories is imported into the runtime.
- Crawled content is untrusted input; instructions inside it cannot override system policy.
- License metadata is not legal approval; ambiguous, missing, or incompatible licenses block reuse pending review.
- Dependency installs and tests run in isolated environments; network is off by default.
- No autonomous merge, production deployment, or privilege escalation.
- Skill proposals are data until validated and approved; a skill cannot grant itself permissions.
- Preserve a single intelligence core; use bounded specialist task contracts, not a swarm of independently trained models.
- Research and market workflows remain offline/historical or paper simulation. No broker integration or order execution.

## Milestones

### M0 — Intake and provenance (started)
- [x] GitHub URL allowlist and canonicalization
- [x] Review checklist and explicit default-deny gates
- [x] API endpoint and regression tests
- [x] Public GitHub repository metadata fetch with redirects disabled and response-size bounds
- [x] Default-branch commit SHA pinning in metadata response
- [ ] GitHub API rate-limit/backoff policy and durable cache
- [ ] License text and NOTICE capture (SPDX metadata alone remains insufficient)

### M1 — Repository crawler and mapper
- [x] Basic GitHub REST metadata adapter with fixed API host and URL validation
- [ ] GitHub API request budget, pagination cap, and durable cache
- [ ] Repository tree manifest and file-type allowlist
- [ ] README/docs extraction and dependency inventory
- [ ] Source provenance records and content hashes
- [ ] Prompt-injection/untrusted-content isolation

### M2 — Reverse-engineering and adaptation
- [ ] Architecture/API/dependency graph report
- [ ] Static security and suspicious-install-script review
- [ ] Component compatibility scoring with evidence
- [ ] Minimal patch generator and upstream attribution template

### M3 — Skill learning
- [ ] Skill proposal schema and versioned registry
- [ ] Skill provenance and source/license metadata
- [ ] Skill evaluation harness and task benchmark
- [ ] Regression/quality threshold and human activation approval

### M4 — Self-building loop
- [ ] Disposable branch/workspace per proposed change
- [ ] Automated tests, static analysis, dependency audit
- [ ] Baseline-vs-candidate scorecard
- [ ] Approval-based promotion and rollback
- [ ] Learning from failure reports without silently changing production behavior

### M5 — Controlled adaptation
- [ ] Durable research queue and scheduled discovery
- [ ] Tool/skill selection based on measured success and cost
- [ ] Drift detection and periodic evaluation
- [ ] Audit dashboard: source, skill, patch, evaluation, approval, rollback

## Completion criteria

Do not mark the system “self-learning” or “self-building” as complete until it demonstrates repeated, reproducible cycles where it:

1. discovers and pins a source,
2. explains what it learned with source references,
3. proposes a minimal adaptation,
4. passes isolated tests and benchmarks,
5. receives required approval,
6. promotes safely,
7. detects a regression and rolls back when intentionally tested.

A large skill count, repository cloning, generated code, or successful one-off demo is not sufficient evidence of autonomous learning.
