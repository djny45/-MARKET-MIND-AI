import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from './apiClient'

/**
 * Four-market terminal board.
 *
 * Renders exactly what the backend verified: one panel per market group, one
 * row per quote, with the source, both timestamps and the status label. It
 * never computes a price, never averages markets, and never hides an
 * UNAVAILABLE row — a market with no usable observation is shown as such.
 */

export type TerminalQuote = {
  symbol: string
  name: string
  asset_class: string
  market_group: string | null
  exchange: string
  currency: string
  instrument_id: string | null
  last: number | null
  bid: number | null
  ask: number | null
  change_pct: number | null
  timestamp: string
  retrieved_at: string
  status: string
  status_label: string
  source: string
  quote_type: string
  delay_seconds: number | null
  reason: string | null
  age_seconds: number
  stale: boolean
  max_age_seconds: number | null
  exchange_timezone: string | null
  timestamp_exchange_local: string | null
}

export type TerminalMarket = {
  market_group: string
  market_status: string
  headline: string
  requested: number
  usable_count: number
  unavailable_count: number
  stale_count: number
  status_counts: Record<string, number>
  coverage_ratio: number
  adapter: {
    name: string
    preferred_status: string
    requires_attestation: boolean
    licensing_note: string
    limitations: string[]
  }
  quotes: TerminalQuote[]
  note?: string
}

export type TerminalSnapshot = {
  generated_at: string
  mode: string
  market_groups: string[]
  markets: TerminalMarket[]
  totals: { markets: number; quotes: number; usable: number; unavailable: number; stale: number }
  legend: { labels: Array<{ status: string; label: string; max_age_seconds: number | null; meaning: string }>; stale_rule: string }
  providers: { note: string; live_claims_require_attestation: boolean }
  attested_sources: string[]
  execution: { paper_trading: boolean; broker_execution: boolean; real_money: boolean }
  cache?: { hit: boolean; age_seconds: number; ttl_seconds: number }
}

const MARKET_TITLES: Record<string, string> = {
  us: 'UNITED STATES',
  india: 'INDIA · NSE / BSE',
  forex: 'FOREX · OTC',
  crypto: 'CRYPTOCURRENCY',
}

const MARKET_SUBTITLES: Record<string, string> = {
  us: 'NYSE · NASDAQ · ETFs · indices',
  india: 'NSE · BSE equities and indices',
  forex: 'ECB daily reference fixing',
  crypto: 'Aggregated public spot snapshot',
}

/** Map a status to the CSS class used for its badge. */
export function statusClass(status: string): string {
  switch (status) {
    case 'live': return 'q-live'
    case 'delayed': return 'q-delayed'
    case 'historical': return 'q-historical'
    case 'synthetic': return 'q-synthetic'
    default: return 'q-unavailable'
  }
}

/** Format an age in seconds as a compact human string. */
export function formatAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

/** Format a price without inventing precision for an unavailable row. */
export function formatLast(quote: Pick<TerminalQuote, 'last' | 'currency' | 'status'>): string {
  if (quote.last === null || quote.last === undefined) return '—'
  if (!Number.isFinite(quote.last)) return '—'
  const decimals = quote.last >= 1000 ? 2 : quote.last >= 1 ? 4 : 6
  return `${quote.last.toLocaleString('en-US', {
    minimumFractionDigits: 2, maximumFractionDigits: decimals,
  })} ${quote.currency}`
}

export function formatChange(value: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

type Props = { api: string; onSelectSymbol?: (symbol: string, marketGroup: string) => void }

export default function FourMarketTerminal({ api, onSelectSymbol }: Props) {
  const [snapshot, setSnapshot] = useState<TerminalSnapshot | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const load = useCallback(async (refresh = false) => {
    setBusy(true)
    setError('')
    try {
      const suffix = refresh ? '?refresh=true' : ''
      const response = await apiFetch(`${api}/api/terminal/four-market${suffix}`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Terminal request failed (${response.status})`)
      setSnapshot(body as TerminalSnapshot)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Terminal request failed')
      setState('error')
    } finally {
      setBusy(false)
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => { void load(true) }, 60_000)
    return () => clearInterval(timer)
  }, [autoRefresh, load])

  const totals = snapshot?.totals
  const marketRows = useMemo(() => snapshot?.markets ?? [], [snapshot])

  return (
    <section className="four-market" aria-label="Four-market research terminal">
      <div className="four-market-head">
        <div>
          <span className="eyebrow">MARKET-MIND-AI / FOUR-MARKET TERMINAL</span>
          <h1>United States · India · Forex · Crypto</h1>
          <p>
            Verified observations from four public adapters. Every row shows its source,
            event time, retrieval time and a status label bound to operator attestation.
          </p>
        </div>
        <div className="four-market-actions">
          <label className="auto-refresh">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={event => setAutoRefresh(event.target.checked)}
            />
            AUTO-REFRESH 60s
          </label>
          <button
            type="button"
            className="soft-btn"
            onClick={() => void load(true)}
            disabled={busy}
          >
            {busy ? 'FETCHING…' : 'REFRESH BOARD'}
          </button>
        </div>
      </div>

      {state === 'error' && <p className="news-error" role="alert">{error}</p>}
      {state === 'loading' && <small role="status">LOADING VERIFIED QUOTES…</small>}

      {snapshot && (
        <>
          <div className="four-market-strip" role="status" aria-live="polite">
            <span className={`status-chip ${totals && totals.usable > 0 ? 'status-ok' : 'status-off'}`}>
              {totals?.usable ?? 0} USABLE / {totals?.quotes ?? 0} ROWS
            </span>
            <span>{totals?.unavailable ?? 0} UNAVAILABLE</span>
            <span>{totals?.stale ?? 0} STALE</span>
            <span>GENERATED {snapshot.generated_at}</span>
            {snapshot.cache && (
              <span>{snapshot.cache.hit ? `CACHED ${formatAge(snapshot.cache.age_seconds)}` : 'FRESH FETCH'}</span>
            )}
            {(snapshot.attested_sources || []).length > 0
              ? <span>ATTESTED: {snapshot.attested_sources.join(', ')}</span>
              : <span>NO ATTESTED SOURCE — LIVE/DELAYED UNAVAILABLE</span>}
          </div>

          <div className="four-market-grid">
            {marketRows.map(market => (
              <article
                key={market.market_group}
                className={`market-panel market-${market.market_status}`}
                aria-label={`${MARKET_TITLES[market.market_group] || market.market_group} market`}
              >
                <header className="market-head">
                  <div>
                    <b>{MARKET_TITLES[market.market_group] || market.market_group.toUpperCase()}</b>
                    <small>{MARKET_SUBTITLES[market.market_group] || market.adapter.name}</small>
                  </div>
                  <div className="market-badges">
                    <span className={`market-status ${market.market_status}`}>{market.headline}</span>
                    <small>{market.usable_count}/{market.requested} usable</small>
                  </div>
                </header>

                <div className="market-adapter">
                  <span>ADAPTER <b>{market.adapter.name}</b></span>
                  <span>BEST LABEL <b>{market.adapter.preferred_status.toUpperCase()}</b></span>
                  <span>{market.adapter.requires_attestation ? 'ATTESTATION REQUIRED' : 'NO ATTESTATION REQUIRED'}</span>
                </div>

                {market.quotes.length === 0 ? (
                  <p className="research-note">
                    {market.note || 'No reference instrument is registered for this market.'}
                  </p>
                ) : (
                  <table className="quote-table">
                    <caption className="visually-hidden">
                      {MARKET_TITLES[market.market_group]} quotes with source and freshness
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">SYMBOL</th>
                        <th scope="col">LAST</th>
                        <th scope="col">CHG</th>
                        <th scope="col">STATUS</th>
                        <th scope="col">SOURCE</th>
                        <th scope="col">EVENT / RETRIEVED</th>
                      </tr>
                    </thead>
                    <tbody>
                      {market.quotes.map(quote => (
                        <tr key={`${quote.symbol}-${quote.source}`} className={quote.stale ? 'quote-stale' : undefined}>
                          <th scope="row">
                            <button
                              type="button"
                              className="symbol-link"
                              onClick={() => onSelectSymbol?.(quote.symbol, market.market_group)}
                              title={`${quote.name} · ${quote.exchange}`}
                            >
                              {quote.symbol}
                            </button>
                            <small>{quote.exchange} · {quote.quote_type}</small>
                          </th>
                          <td>{formatLast(quote)}</td>
                          <td className={quote.change_pct !== null && quote.change_pct < 0 ? 'neg' : 'pos'}>
                            {formatChange(quote.change_pct)}
                          </td>
                          <td>
                            <span className={`quote-badge ${statusClass(quote.status)}`}>
                              {quote.status_label}
                            </span>
                            {quote.stale && <small className="stale-flag">STALE {formatAge(quote.age_seconds)}</small>}
                          </td>
                          <td><small>{quote.source}</small></td>
                          <td>
                            <small>{quote.timestamp}</small>
                            {quote.timestamp_exchange_local && (
                              <small title={quote.exchange_timezone || undefined}>
                                {quote.timestamp_exchange_local}
                              </small>
                            )}
                            <small>{quote.retrieved_at}</small>
                            <small>AGE {formatAge(quote.age_seconds)}</small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {market.note && market.quotes.length > 0 && (
                  <p className="research-note">{market.note}</p>
                )}
                {market.unavailable_count > 0 && (
                  <p className="market-warning">
                    {market.unavailable_count} instrument(s) reported UNAVAILABLE.
                    No price is implied for those rows.
                  </p>
                )}
                <details className="market-licensing">
                  <summary>LICENSING &amp; LIMITATIONS</summary>
                  <p>{market.adapter.licensing_note}</p>
                  <ul>
                    {market.adapter.limitations.map(item => <li key={item}>{item}</li>)}
                  </ul>
                </details>
              </article>
            ))}
          </div>

          <div className="four-market-footer">
            <div className="legend" aria-label="Status label legend">
              <b>STATUS LABELS</b>
              {(snapshot.legend?.labels || []).map(item => (
                <span key={item.status} className={`quote-badge ${statusClass(item.status)}`} title={item.meaning}>
                  {item.label}
                </span>
              ))}
            </div>
            <p className="research-note">{snapshot.legend.stale_rule}</p>
            <p className="research-note">{snapshot.providers?.note || 'Provider capabilities unavailable.'}</p>
            <p className="research-note">
              EXECUTION · BROKER {String(snapshot.execution?.broker_execution ?? false).toUpperCase()} ·
              REAL MONEY {String(snapshot.execution?.real_money ?? false).toUpperCase()} ·
              RESEARCH AND DISPLAY ONLY
            </p>
          </div>
        </>
      )}
    </section>
  )
}
