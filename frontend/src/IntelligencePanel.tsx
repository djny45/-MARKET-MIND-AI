import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from './apiClient'
import type { FlowDot } from './PriceChart'

/** Research panel for the integrated public-exchange intelligence endpoints.
 *
 * This EXTENDS the existing terminal with data from the existing provider
 * architecture. It is not a second terminal, chart engine or analytics system.
 */
type Props = { api: string }

type VenueRow = {
  venue: string
  status: string
  status_label: string
  last: number | null
  source: string
  reason?: string | null
  age_seconds: number
  stale: boolean
}

type Payload = {
  generated_at: string
  venues: VenueRow[]
  funding: Record<string, unknown>
  depth: Record<string, unknown>
  sentiment: Record<string, unknown>
  gold: Record<string, unknown>
  flow: { summary: Record<string, unknown>; dots: { dots: FlowDot[]; count: number } }
  brokers: Record<string, unknown>
  execution: { broker_execution: boolean; real_money: boolean }
  licensing: Record<string, unknown>
}

export default function IntelligencePanel({ api }: Props) {
  const [data, setData] = useState<Payload | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setState('loading')
    setError('')
    try {
      const response = await apiFetch(`${api}/api/intelligence/board`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Intelligence request failed (${response.status})`)
      if (!Array.isArray(body.venues)) {
        // An unrecognised/default response is not a board. Render nothing
        // rather than crashing the surrounding terminal tree.
        setData(null)
        setState('ready')
        return
      }
      setData(body as Payload)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Intelligence request failed')
      setState('error')
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  const fmt = (value: unknown) =>
    value === null || value === undefined ? '—'
      : typeof value === 'number' ? value.toLocaleString('en-US', { maximumFractionDigits: 6 })
        : String(value)

  return (
    <section className="intel-panel" aria-label="Exchange intelligence panel">
      <div className="intel-head">
        <div>
          <span className="eyebrow">MARKET-MIND-AI / EXCHANGE INTELLIGENCE</span>
          <h2>Crypto · Gold · Order Flow · Sentiment</h2>
          <p>Official public endpoints only. Every observation carries source, event time and retrieval time. Third-party undocumented endpoints are not used.</p>
        </div>
        <button type="button" className="soft-btn" onClick={() => void load()} disabled={state === 'loading'}>
          {state === 'loading' ? 'LOADING…' : 'REFRESH INTELLIGENCE'}
        </button>
      </div>

      {state === 'error' && <p className="news-error" role="alert">{error}</p>}

      {data && data.venues.length > 0 && (
        <>
          <div className="intel-grid">
            {(data.venues || []).map(row => (
              <article key={row.venue} className={`intel-card ${row.status}`}>
                <b>{row.venue.toUpperCase()}</b>
                <span className="quote-badge q-historical">{row.status_label}</span>
                <strong>{fmt(row.last)}</strong>
                <small>SOURCE {row.source}</small>
                <small>AGE {row.age_seconds}s · STALE {String(row.stale).toUpperCase()}</small>
                {row.reason && <small className="news-error">{row.reason}</small>}
              </article>
            ))}
          </div>

          <div className="intel-details">
            <div><b>FUNDING & OPEN INTEREST</b><pre>{JSON.stringify(data.funding, null, 2)}</pre></div>
            <div><b>ORDER-BOOK DEPTH</b><pre>{JSON.stringify(data.depth, null, 2)}</pre></div>
            <div><b>FEAR & GREED</b><pre>{JSON.stringify(data.sentiment, null, 2)}</pre></div>
            <div><b>GOLD (TOKENIZED)</b><pre>{JSON.stringify(data.gold, null, 2)}</pre></div>
            <div><b>EXECUTED TRADE FLOW</b><pre>{JSON.stringify(data.flow?.summary || {}, null, 2)}</pre></div>
            <div><b>LIQUIDATION / FLOW MARKERS</b><pre>{JSON.stringify({ count: data.flow?.dots?.count || 0, dots: (data.flow?.dots?.dots || []).slice(0, 10) }, null, 2)}</pre></div>
          </div>

          <div className="intel-boundary">
            <p className="research-note">
              BROKER CONNECTIONS: {fmt((data.brokers as { live_broker_data_available?: boolean })?.live_broker_data_available)} ·
              BROKER EXECUTION {String(data.execution.broker_execution).toUpperCase()} ·
              REAL MONEY {String(data.execution.real_money).toUpperCase()}
            </p>
            <p className="research-note">
              MARKET-MIND-AI is a research and educational analytics platform, not a broker or
              investment adviser. No SEBI registration or regulatory approval is claimed.
              Sample, historical and delayed data are labelled explicitly; no broker
              credentials are stored or sent to this backend or to research agents.
            </p>
            <p className="research-note">
              LICENSING: {fmt(data.licensing?.live_claims_require_attestation)} ·
              TREDYE ENDPOINTS USED {fmt(data.licensing?.tredye_endpoints_used)}
            </p>
          </div>
        </>
      )}
    </section>
  )
}
