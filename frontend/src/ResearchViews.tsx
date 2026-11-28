import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from './apiClient'

/** Research view switcher INSIDE the existing intelligence panel.
 * Reuses existing backend APIs; no second terminal, chart engine or analytics
 * system is created. Each view shows source, timestamps and data status.
 */
type Props = { api: string }

const VIEWS = [
  { id: 'overview', label: 'OVERVIEW' },
  { id: 'money-flow', label: 'MONEY FLOW' },
  { id: 'order-book', label: 'ORDER BOOK' },
  { id: 'oi-funding', label: 'OI / FUNDING / BASIS' },
  { id: 'options', label: 'OPTIONS' },
  { id: 'liquidations', label: 'LIQUIDATIONS' },
  { id: 'backtesting', label: 'BACKTESTING' },
] as const

type ViewId = typeof VIEWS[number]['id']

export default function ResearchViews({ api }: Props) {
  const [view, setView] = useState<ViewId>('overview')
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState('')
  const [agentId, setAgentId] = useState('worker_001')
  const [symbol, setSymbol] = useState('BTCUSDT')

  const load = useCallback(async () => {
    setState('loading')
    setError('')
    const routes: Record<ViewId, string> = {
      overview: '/api/intelligence/board',
      'money-flow': '/api/intelligence/order-flow',
      'order-book': '/api/intelligence/order-book/replay',
      'oi-funding': '/api/intelligence/okx/derivatives',
      options: '/api/intelligence/deribit/options',
      liquidations: '/api/intelligence/liquidations',
      backtesting: `/api/paper/backtest/run?agent_id=${encodeURIComponent(agentId)}&symbol=${encodeURIComponent(symbol)}`,
    }
    try {
      const response = await apiFetch(`${api}${routes[view]}`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`)
      setData(body as Record<string, unknown>)
      setState('idle')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Research view unavailable')
      setData(null)
      setState('error')
    }
  }, [api, view, agentId, symbol])

  useEffect(() => { void load() }, [load])

  return (
    <section className="research-views" aria-label="Market structure research views">
      <div className="research-views-head">
        <b>RESEARCH VIEWS</b>
        <div className="research-view-tabs" role="tablist">
          {VIEWS.map(item => (
            <button
              key={item.id} type="button" role="tab"
              aria-selected={view === item.id}
              className={view === item.id ? 'active' : ''}
              onClick={() => { setView(item.id); setData(null) }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {view === 'backtesting' && (
        <div className="research-view-controls">
          <label>AGENT <input aria-label="Backtest agent" value={agentId} onChange={e => setAgentId(e.target.value)} /></label>
          <label>SYMBOL <input aria-label="Backtest symbol" value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} /></label>
        </div>
      )}

      <div className="research-view-actions">
        <button type="button" className="soft-btn" onClick={() => void load()} disabled={state === 'loading'}>
          {state === 'loading' ? 'LOADING…' : 'LOAD VIEW'}
        </button>
        <small>Backend historical analytical capability only. No broker execution or autonomous trading.</small>
      </div>

      {state === 'error' && <p className="news-error" role="alert">{error}</p>}
      {data && (
        <div className="research-view-result">
          <pre data-testid="research-view-payload">{JSON.stringify(data, null, 2)}</pre>
          <p className="research-note">
            Source, event timestamps and status labels are preserved in the payload.
            Historical and derived values are never presented as live quotes.
          </p>
        </div>
      )}
    </section>
  )
}
