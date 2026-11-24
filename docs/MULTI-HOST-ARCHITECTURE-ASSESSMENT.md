# Multi-host queue and supervisor assessment (2026-11-24)

Status: **assessment only**. Multi-host execution is **NOT implemented** and is
not claimed. The shipped system remains a single-host SQLite research queue.

## 1. Current architecture

- `analytical_agent_tasks` persists tasks in SQLite (`market_mind.db`) on the
  shared `market_mind_data` volume. The API enqueues; a dedicated supervisor
  process polls, claims and dispatches bounded batches.
- Claim safety uses an atomic conditional `UPDATE ... WHERE status='queued'`
  with an `execution_token`; result, evaluation, event and learning side effects
  are fenced by that token. This prevents a stale executor from overwriting a
  requeued task's state.
- Supervisor leadership uses a single heartbeat row with an acquired,
  expiring lease and compare-and-swap renewal. The 2026-11-24 fix adds
  conditional acquisition, fenced heartbeats/release, rejection of expired
  renewals, and renewal during long dispatch. It is still a **single-host**
  lease row, not a distributed coordination service.
- SQLite WAL and a busy timeout serialize writers. Two supervisors on the same
  host/database cannot claim the same queued row; the lease prevents concurrent
  leadership under normal operation. Crash recovery relies on lease expiry and
  stale-task requeue.

## 2. What the current design guarantees and what it does not

| Property | Current status |
| --- | --- |
| One queued row claimed once | guaranteed by atomic SQLite claim + token fence |
| Stale executor cannot finalize a requeued task | guaranteed by token-fenced side effects |
| One active supervisor lease while healthy | guaranteed by conditional acquisition/CAS renewal |
| Lease survives a long dispatch | guaranteed by in-dispatch renewal thread |
| Two-process lease race under all schedulings | not fully proven; two-process contract test remains gated by ADR-0001 |
| Global queue across multiple hosts | **not available** (shared SQLite file only) |
| Exactly-once provider calls | **not guaranteed**; at-least-once with token fencing |
| Broker-based backpressure / delivery acknowledgements | **not available** |

## 3. Is distributed execution necessary?

Not for the documented research-only workload: bounded batches, no live trading,
no licensed provider configured, and a single shared intelligence core. Adding a
broker would increase operational surface without a demonstrated throughput or
availability requirement. The safe default is to keep single-host execution and
treat multi-host as an optional future scaling step, not a completion criterion.

It becomes necessary if operators require: horizontal throughput beyond one
supervisor, host-failure tolerance without shared storage, or isolation between
tenants/queues. Those requirements are not present today.

## 4. Architecture proposal (not implemented)

1. Replace the shared SQLite queue with a durable broker: PostgreSQL
   `FOR UPDATE SKIP LOCKED` or Redis Streams with consumer groups, chosen after
   a durability/ops review. Keep SQLite as the local research store, not the
   coordination plane.
2. Represent a task claim as a broker message ID plus a fencing token. Finalize
   side effects only while the token is still current; emit a bounded
   `task_lease_lost` diagnostic when a discarded attempt completes.
3. Give each supervisor a unique instance ID and a broker-native lease
   (e.g. PostgreSQL advisory lock or Redis SET NX PX with Lua release). Renew
   during long work; release with CAS on shutdown; never delete another
   owner's lock.
4. Make provider calls idempotent where possible (request ID / dedupe key) so
   at-least-once delivery does not double bill or double record.
5. Preserve the research-only boundary: no wallet, signing, broker routing or
   live order paths; the broker only coordinates research tasks.
6. Keep single-host SQLite mode as the default deployment and document the
   migration path rather than silently switching.

## 5. Test strategy before any multi-host claim

- Two-process contract test with distinct PIDs sharing a real coordinator:
  exactly one lease acquired, loser performs no recovery/dispatch, takeover
  only after expiry or explicit release.
- Kill -9 mid-dispatch: stale lease expires, task requeues once, stale token
  cannot finalize, new executor completes with a single final result.
- Concurrent claim test: N workers, one queued row, exactly one successful
  claim and one provider call (with idempotency disabled to expose duplicates).
- Partition/failover test for the chosen broker, including recovery of
  in-flight messages and bounded duplication.
- Soak test with long-running dispatch where lease renewal must remain valid.

Until these tests exist and pass on a real multi-host-capable coordinator,
multi-host support remains a proposal only.
