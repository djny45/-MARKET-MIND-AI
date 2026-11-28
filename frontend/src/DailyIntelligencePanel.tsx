import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from './apiClient'

/** Daily Research Cycle panel — additive, uses existing backend APIs only. */
type Props = { api: string }

type Observation = {
  market_group: string
  data_status: string
  status_label: string
  headline: string
  usable_count: number
  unavailable_count: number
  stale_count: number
  source?: string
  reason?: string
}

type DailyCycle = {
  cycle_id: string
  cycle_date: string
  status: string
  generated_at: string
  observations: Observation[]
  execution: {
    registered_agents: number
    agents_assigned_tasks: number
    agents_executed_tasks: number
    agents_completed_tasks: number
    agents_failed: number
    agents_skipped: number
    concurrent_execution_count: number | null
    tasks_completed: number
    tasks_pending: number
    metric_definition: string
  }
  quality_scorecard: {
    observation_coverage: number | null
    usable_observations: number
    unavailable_observations: number
    stale_observations: number
    agent_participation: number | null
    data_labels_verified: boolean
    scorecard_note: string
  }
  consensus: { available: boolean; disagreement_present?: boolean; direction_counts?: Record<string, number> }
  zulip_notification: { status: string }
  archive: { archived: Array<{ market_group: string; revision: number }> }
  duplicate_cycle_detected: boolean
}

type ArchiveRow = {
  cycle_id: string
  cycle_date: string
  market_group: string
  revision: number
  content_sha256: string
  parent_sha256: string | null
  created_at: string
}

const pct = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`

export default function DailyIntelligencePanel({ api }: Props) {
  const [cycle, setCycle] = useState<DailyCycle | null>(null)
  const [archive, setArchive] = useState<ArchiveRow[]>([])
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState('')
  const [date, setDate] = useState('')

  const loadArchive = useCallback(async () => {
    try {
      const response = await apiFetch(`${api}/api/daily/archive?limit=20`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (response.ok) setArchive(body.rows || [])
    } catch { /* archive is optional */ }
  }, [api])

  const run = useCallback(async () => {
    setState('loading')
    setError('')
    try {
      const response = await apiFetch(`${api}/api/daily/run`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: date || undefined, publish_zulip: true }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Cycle failed (${response.status})`)
      setCycle(body as DailyCycle)
      setState('idle')
      await loadArchive()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Daily cycle unavailable')
      setState('error')
    }
  }, [api, date, loadArchive])

  useEffect(() => { void loadArchive() }, [loadArchive])

  return (
    <section className="daily-panel" aria-label="Daily intelligence research cycle">
      <div className="daily-head">
        <div>
          <span className="eyebrow">MARKET-MIND-AI / DAILY INTELLIGENCE</span>
          <h2>Daily research cycle</h2>
          <p>Deterministic, evidence-driven research over the existing four-market architecture and 550-agent registry. No Zulip or provider outage can stop it.</p>
        </div>
        <div className="daily-controls">
          <label>DATE (UTC) <input aria-label="Cycle date" placeholder="YYYY-MM-DD" value={date} onChange={e => setDate(e.target.value)} /></label>
          <button type="button" className="soft-btn" onClick={() => void run()} disabled={state === 'loading'}>
            {state === 'loading' ? 'RUNNING…' : 'RUN DAILY CYCLE'}
          </button>
        </div>
      </div>

      {state === 'error' && <p className="news-error" role="alert">{error}</p>}

      {cycle && (
        <>
          <div className="daily-strip" role="status">
            <span>{cycle.cycle_id}</span>
            <span className={`status-chip ${cycle.status === 'completed' ? 'status-ok' : 'status-off'}`}>
              {cycle.status.toUpperCase()}
            </span>
            <span>GENERATED {cycle.generated_at}</span>
            <span>LABELS VERIFIED {String(cycle.quality_scorecard.data_labels_verified).toUpperCase()}</span>
            <span>ZULIP {cycle.zulip_notification.status.toUpperCase()}</span>
            {cycle.duplicate_cycle_detected && <span>DUPLICATE SUPPRESSED</span>}
          </div>

          <div className="daily-grid">
            <div>
              <b>MARKET COVERAGE</b>
              {cycle.observations.map(row => (
                <div className="daily-row" key={row.market_group}>
                  <span>{row.market_group.toUpperCase()}</span>
                  <span className={`quote-badge q-${row.data_status}`}>{row.status_label}</span>
                  <span>{row.headline}</span>
                  <small>{row.source || row.reason || '—'} · usable {row.usable_count} · unavailable {row.unavailable_count} · stale {row.stale_count}</small>
                </div>
              ))}
            </div>
            <div>
              <b>AGENT ACCOUNTABILITY</b>
              <div className="daily-stats">
                <span>REGISTERED {cycle.execution.registered_agents}</span>
                <span>ASSIGNED {cycle.execution.agents_assigned_tasks}</span>
                <span>EXECUTED {cycle.execution.agents_executed_tasks}</span>
                <span>COMPLETED {cycle.execution.agents_completed_tasks}</span>
                <span>FAILED {cycle.execution.agents_failed}</span>
                <span>SKIPPED {cycle.execution.agents_skipped}</span>
                <span>CONCURRENT {cycle.execution.concurrent_execution_count ?? '—'}</span>
                <span>TASKS DONE {cycle.execution.tasks_completed}</span>
                <span>TASKS PENDING {cycle.execution.tasks_pending}</span>
              </div>
              <small>{cycle.execution.metric_definition}</small>
            </div>
            <div>
              <b>QUALITY SCORECARD</b>
              <div className="daily-stats">
                <span>COVERAGE {pct(cycle.quality_scorecard.observation_coverage)}</span>
                <span>PARTICIPATION {pct(cycle.quality_scorecard.agent_participation)}</span>
                <span>STALE {cycle.quality_scorecard.stale_observations}</span>
                <span>CONSENSUS {cycle.consensus.available ? String(cycle.consensus.disagreement_present) : 'UNAVAILABLE'}</span>
              </div>
              <small>{cycle.quality_scorecard.scorecard_note}</small>
            </div>
          </div>
        </>
      )}

      {archive.length > 0 && (
        <details className="daily-archive">
          <summary>DAILY RESEARCH ARCHIVE ({archive.length})</summary>
          {archive.map(row => (
            <div className="daily-row" key={`${row.cycle_id}-${row.market_group}-${row.revision}`}>
              <span>{row.cycle_date}</span><span>{row.market_group.toUpperCase()}</span>
              <span>REV {row.revision}</span><small>{row.content_sha256.slice(0, 16)}</small>
            </div>
          ))}
          <p className="research-note">Append-only version history. No previous report is overwritten.</p>
        </details>
      )}
    </section>
  )
}
