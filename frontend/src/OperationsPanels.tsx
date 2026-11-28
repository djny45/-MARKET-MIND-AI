import { useEffect, useState, type FormEvent } from 'react'
import { apiFetch } from './apiClient'

type LoadState = 'loading' | 'ready' | 'error'

function useResource(api: string, path: string) {
  const [state, setState] = useState<LoadState>('loading')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const load = async () => {
    setState('loading')
    setError('')
    try {
      const response = await apiFetch(api + path, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`)
      setData(body)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request unavailable')
      setState('error')
    }
  }
  useEffect(() => { void load() }, [api, path])
  return { state, data, error, load }
}

function StateLine({ state, error }: { state: LoadState; error: string }) {
  if (state === 'loading') return <small role="status">LOADING…</small>
  if (state === 'error') return <small className="news-error" role="alert">{error}</small>
  return null
}

const HISTORICAL_ONLY = 'Historical descriptive statistics only. Not a forecast, investment return or trading signal.'

function PerformancePanel({ api, kind }: { api: string; kind: 'portfolio' | 'risk' }) {
  const [values, setValues] = useState('100,101,99,103,105')
  const [state, setState] = useState<LoadState | 'idle'>('idle')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const analyse = async (event: FormEvent) => {
    event.preventDefault()
    setState('loading')
    setError('')
    try {
      const parsed = values.split(',').map(v => Number(v.trim())).filter(Number.isFinite)
      if (parsed.length < 3 || parsed.some(v => v <= 0)) throw new Error('Enter at least three positive numbers')
      const response = await apiFetch(api + '/api/analytics/performance', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values: parsed, periods_per_year: 252, risk_free_rate: 0 }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Performance calculation failed')
      setData(body)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Performance calculation failed')
      setState('error')
    }
  }
  const risk = kind === 'risk'
  return (
    <section className="ops-panel" aria-label={risk ? 'Risk analytics' : 'Portfolio research analytics'}>
      <div className="side-label">{risk ? 'RISK ANALYTICS' : 'PORTFOLIO RESEARCH'} <span>LOCAL HISTORICAL INPUT</span></div>
      <small className="research-note">{HISTORICAL_ONLY}</small>
      <form onSubmit={analyse} className="ops-form">
        <label htmlFor="ops-values">CLOSE SERIES (COMMA SEPARATED)</label>
        <input id="ops-values" aria-label="Historical close series" value={values} onChange={e => setValues(e.target.value)} />
        <button type="submit" className="soft-btn research-run" disabled={state === 'loading'}>
          {state === 'loading' ? 'CALCULATING…' : 'CALCULATE'}
        </button>
      </form>
      <StateLine state={state === 'idle' ? 'loading' : state} error={error} />
      {state === 'ready' && data && (
        <div className="aligned-row">
          <b>{risk ? 'MAX DRAWDOWN' : 'CUMULATIVE RETURN'}</b>
          <span>{risk ? `${(data.max_drawdown * 100).toFixed(2)}%` : `${(data.cumulative_return * 100).toFixed(2)}%`}</span>
          <span>VOL {(data.annualized_volatility * 100).toFixed(2)}%</span>
          <small>SHARPE {data.annualized_sharpe?.toFixed(2) || '—'} · SORTINO {data.sortino_per_period?.toFixed(2) || '—'}</small>
        </div>
      )}
    </section>
  )
}

export function PortfolioAnalytics({ api }: { api: string }) { return <PerformancePanel api={api} kind="portfolio" /> }
export function RiskAnalytics({ api }: { api: string }) { return <PerformancePanel api={api} kind="risk" /> }

export function SystemHealthPanel({ api }: { api: string }) {
  const health = useResource(api, '/api/health')
  const ready = useResource(api, '/api/ready')
  const supervisor = useResource(api, '/api/analytical-agent-supervisor/status')
  return (
    <section className="ops-panel" aria-label="System health dashboard">
      <div className="side-label">SYSTEM HEALTH <span>RESEARCH ONLY</span></div>
      <StateLine state={health.state} error={health.error} />
      {health.state === 'ready' && <div className="aligned-row">
        <b>{health.data.status}</b><span>{health.data.service}</span>
        <small>BROKER EXECUTION {String(health.data.broker_execution).toUpperCase()} · PAPER TRADING {String(health.data.paper_trading).toUpperCase()}</small>
      </div>}
      <StateLine state={ready.state} error={ready.error} />
      {ready.state === 'ready' && <small>READINESS: {JSON.stringify(ready.data)}</small>}
      <StateLine state={supervisor.state} error={supervisor.error} />
      {supervisor.state === 'ready' && <small>SUPERVISOR: {supervisor.data.status} · QUEUED {supervisor.data.status_counts?.queued ?? 0}</small>}
    </section>
  )
}

export function ProviderHealthPanel({ api }: { api: string }) {
  const { state, data, error } = useResource(api, '/api/providers/status')
  return (
    <section className="ops-panel" aria-label="Provider health">
      <div className="side-label">PROVIDER HEALTH <span>PROVENANCE</span></div>
      <StateLine state={state} error={error} />
      {state === 'ready' && <>
        <div className="aligned-row"><b>{data.status}</b><span>{data.live_providers?.length ?? 0} LIVE</span></div>
        <small>{data.market_data_note}</small>
        {(data.available_adapters || []).map((a: any) => <small key={a.name}>{a.name}: {a.data_status} · {a.purpose}</small>)}
      </>}
    </section>
  )
}

export function AuditEventsPanel({ api }: { api: string }) {
  const { state, data, error, load } = useResource(api, '/api/security/audit-events?limit=20')
  return (
    <section className="ops-panel" aria-label="Security audit events">
      <div className="side-label">AUDIT &amp; SECURITY EVENTS <span>BOUNDED</span></div>
      <button type="button" className="soft-btn research-run" onClick={load}>REFRESH EVENTS</button>
      <StateLine state={state} error={error} />
      {state === 'ready' && (data.events || []).length === 0 && <small className="research-note">No events recorded.</small>}
      {(data?.events || []).map((event: any) => (
        <div className="aligned-row" key={event.event_id}>
          <b>{event.event_type}</b><span>{event.outcome}</span><small>{event.actor_role || 'unknown'} · {event.timestamp}</small>
        </div>
      ))}
    </section>
  )
}

export function BackupStatusPanel({ api }: { api: string }) {
  const { state, data, error, load } = useResource(api, '/api/backup/status')
  return (
    <section className="ops-panel" aria-label="Backup and recovery status">
      <div className="side-label">BACKUP STATUS <span>INVENTORY ONLY</span></div>
      <button type="button" className="soft-btn research-run" onClick={load}>REFRESH BACKUPS</button>
      <StateLine state={state} error={error} />
      {state === 'ready' && <>
        <div className="aligned-row"><b>{data.backup_count} BACKUPS</b><small>{data.directory}</small></div>
        <small>{data.note}</small>
        {(data.backups || []).map((b: any) => <small key={b.name}>{b.name} · {b.bytes} bytes · sha256 {b.sha256_sidecar ? 'present' : 'missing'}</small>)}
      </>}
    </section>
  )
}

export function SettingsPanel({ api }: { api: string }) {
  const config = useResource(api, '/api/system/config')
  const validation = useResource(api, '/api/environment-validation')
  return (
    <section className="ops-panel" aria-label="Settings and configuration">
      <div className="side-label">SETTINGS <span>READ ONLY · NO SECRETS</span></div>
      <StateLine state={config.state} error={config.error} />
      {config.state === 'ready' && <small>{JSON.stringify(config.data.checks || config.data)}</small>}
      <StateLine state={validation.state} error={validation.error} />
      {validation.state === 'ready' && <small>{JSON.stringify(validation.data.checks || validation.data)}</small>}
      <small className="research-note">Operator-managed via a 0600 environment file. No credential is editable from the UI.</small>
    </section>
  )
}
