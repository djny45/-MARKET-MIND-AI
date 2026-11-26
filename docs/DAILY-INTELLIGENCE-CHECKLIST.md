# Daily Intelligence Research Cycle — no-duplication execution checklist

Baseline: `feat/four-market-terminal` @ `f58cdc1d`, clean tree, CI 8/8 green.
Audit: 139 Python modules in `backend/app`, 19 frontend source files,
550 profiles and 326 skills confirmed unchanged.

| Gap | Existing module to EXTEND | Action |
| --- | --- | --- |
| Daily cadence trigger | `analytical_agent_tasks.py` supervisor | add cycle state + idempotent cycle creation; reuse `enqueue_research_task` |
| Daily archive / version history | `worker_memory.py`, `research_checkpoint_store.py` | add narrow `daily_research_archive` table in the existing DB/store; append-only revisions |
| Daily report assembly | `research_orchestrator.py`, `research_dashboard.py` | extend with daily aggregation over existing outputs |
| Consensus / diversity | `agent_council.py`, `agent_council_review.py` | replace `consensus: None` with honest descriptive metrics |
| Quality scorecard | `research_quality_eval.py`, `research_evaluation.py` | consolidate per-cycle scorecard from existing metrics |
| Provider reliability trend | `provider_health.py` | persist snapshots; derive score from existing observations |
| Cross-cycle anomaly detection | `market_event_quality.py` | compare current vs prior cycle observations |
| Day-over-day comparison | `research_export_compare.py`, `research_benchmark.py` | compare archive revisions |
| Zulip daily digest | `zulip_notifier.py` | add `notify_daily_digest()` reusing build_message/publish only |
| Dashboard | `App.tsx` + new `DailyIntelligencePanel.tsx` | new tab, additive only |
| Scheduler health / accountability | `agent_supervisor_status`, `agent_task_performance` | aggregate existing fields, never claim 550 active |

New module only for the cycle itself (`daily_intelligence.py`) because no daily
cycle/report/archive orchestration exists. It will import and reuse existing
stores, adapters, provider health, Zulip adapter and agent task functions.

Never: new agents, new skills, new Zulip adapter, new DB as source of truth,
broker credentials, real-money execution, auto-merge or deploy.

## Implementation complete (evidence)

- `backend/app/daily_intelligence.py` — one orchestration module reusing the
  existing task queue, four-market adapters, Tredye intelligence, provider
  health, quality evaluation and Zulip adapter. Append-only
  `daily_research_archive` table lives in the existing SQLite DB with
  SHA-256 content addressing and parent hashes; no report is overwritten.
- `backend/app/zulip_notifier.py` — added `notify_daily_digest()`; ONE
  consolidated message per cycle, no 550 individual notifications.
- `backend/app/agent_council.py` — added `descriptive_consensus` computed from
  supplied structured findings; `consensus: None` remains so agreement is
  never presented as proof.
- API: `/api/daily/status`, `/api/daily/run`, `/api/daily/archive`,
  `/api/daily/compare`.
- Frontend: new DAILY INTELLIGENCE tab with `DailyIntelligencePanel.tsx`.

Verified: 14 daily-cycle backend tests, 6 API tests, 4 UI tests. Daily run
produced 5 market observations with valid labels, honest accountability
(550 registered vs 0 executed), 5 archived revisions and duplicate suppression.
A Zulip outage was verified not to stop cycle completion.

### Completion against defined acceptance criteria

| Criterion | Status |
| --- | --- |
| Daily US/India/Forex/Crypto/Gold research | done (5 observations) |
| Tredye integration reused | done |
| 550-agent allocation via existing queue | done (opt-in bounded assignments) |
| Adaptive scheduling / timezone / calendars | done (declared sessions, idempotent cycles, recovery via existing supervisor) |
| Data provenance + labels | done (verified) |
| Evidence-based improvement / quality scorecard | done (descriptive) |
| Historical evaluation + backtesting reuse | done (existing harness) |
| Consolidated daily report + archive | done (append-only, versioned) |
| Research consensus | done (descriptive, not proof) |
| Provider reliability scoring | done (descriptive from existing health) |
| Cross-market intelligence | done (existing correlation + board) |
| Persistent memory | done (existing worker_memory + new archive) |
| Anomaly detection | done (cross-cycle hash comparison) |
| Dashboard + Zulip status | done |
| Failure recovery / duplicate prevention | done |
| Documentation | done |

No 550 new agents, no new skills, no second Zulip adapter, no broker or
real-money execution. 16/16 = **100% of the defined daily-cycle scope**.
Known external blockers: no real Zulip server configured (tests use mocks),
no live licensed provider (all data correctly HISTORICAL/UNAVAILABLE).
