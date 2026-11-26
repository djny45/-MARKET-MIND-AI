import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from './apiClient'
import PriceChart from './PriceChart'

/**
 * Four-market OHLCV chart panel.
 *
 * Ingests normalized candles through the backend's four-market adapter, then
 * displays them with full provenance. It never computes or fills a candle: an
 * empty or failed response is rendered as such.
 */
export type Bar = {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  source?: string
  status?: string
  retrieved_at?: string
}

export type IngestionResult = {
  mode: string
  symbol: string
  market_group: string
  venue: string | null
  interval: string
  source: string
  status: string
  status_label: string
  retrieved_at: string
  observation_count: number
  first_timestamp: string | null
  last_timestamp: string | null
  exchange_timezone: string | null
  warnings: string[]
  bars: Bar[]
  storage: { inserted?: number; updated?: number; symbol?: string } | null
  execution: { broker_execution: boolean; real_money: boolean }
}

type IntervalRow = {
  market_group: string
  source: string
  supported_intervals: string[]
  exchange_timezone: string | null
  note: string
}

type Props = { api: string; markets?: string[] }

type Analytics = {
  realized_volatility: { per_observation: number; observations: number } | null
  average_volume: number | null
  max_volume: number | null
  observation_count: number
}

const TITLES: Record<string, string> = {
  us: 'UNITED STATES', india: 'INDIA · NSE / BSE',
  forex: 'FOREX · OTC', crypto: 'CRYPTOCURRENCY',
}

const SYMBOLS: Record<string, { value: string; venue: string }[]> = {
  us: [
    { value: 'AAPL', venue: 'NASDAQ' }, { value: 'MSFT', venue: 'NASDAQ' },
    { value: 'NVDA', venue: 'NASDAQ' }, { value: 'SPY', venue: 'NYSE' },
    { value: 'SPX', venue: 'INDEX' },
  ],
  india: [
    { value: 'RELIANCE', venue: 'NSE' }, { value: 'TCS', venue: 'NSE' },
    { value: 'INFY', venue: 'NSE' }, { value: 'NIFTY50', venue: 'NSE' },
    { value: 'SENSEX', venue: 'BSE' },
  ],
  forex: [
    { value: 'EURUSD', venue: 'OTC' }, { value: 'USDINR', venue: 'OTC' },
    { value: 'USDJPY', venue: 'OTC' }, { value: 'GBPUSD', venue: 'OTC' },
  ],
  crypto: [
    { value: 'BTCUSD', venue: 'Multi-venue' }, { value: 'ETHUSD', venue: 'Multi-venue' },
    { value: 'SOLUSD', venue: 'Multi-venue' },
  ],
}

export default function FourMarketChart({ api, markets }: Props) {
  const groups = markets && markets.length ? markets : ['us', 'india', 'forex', 'crypto']
  const [marketGroup, setMarketGroup] = useState(groups[0])
  const [symbol, setSymbol] = useState(SYMBOLS[groups[0]][0].value)
  const [interval, setInterval] = useState('1d')
  const [result, setResult] = useState<IngestionResult | null>(null)
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [intervals, setIntervals] = useState<Record<string, IntervalRow>>({})
  const [state, setState] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch(`${api}/api/terminal/bars/intervals`, { credentials: 'include' })
      .then(r => r.json())
      .then(body => {
        const rows: IntervalRow[] = Array.isArray(body?.intervals) ? body.intervals : []
        setIntervals(Object.fromEntries(rows.map(row => [row.market_group, row])))
      })
      .catch(() => setIntervals({}))
  }, [api])

  const supportedIntervals = useMemo(() => {
    const row = intervals[marketGroup]
    if (!row) return ['15m', '1h', '4h', '1d']
    return row.supported_intervals
  }, [intervals, marketGroup])

  useEffect(() => {
    if (!supportedIntervals.includes(interval)) setInterval(supportedIntervals[0])
  }, [supportedIntervals, interval])

  const load = useCallback(async () => {
    setState('loading')
    setError('')
    try {
      const venue = SYMBOLS[marketGroup]?.find(item => item.value === symbol)?.venue || ''
      const query = new URLSearchParams({
        symbol, market_group: marketGroup, interval, limit: '200', venue,
      })
      const response = await apiFetch(`${api}/api/terminal/bars/ingest?${query.toString()}`, {
        method: 'POST', credentials: 'include',
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Ingestion failed (${response.status})`)
      if (!Array.isArray(body.bars) || body.bars.length === 0) {
        throw new Error('Provider returned no usable candles; nothing is plotted.')
      }
      setResult(body as IngestionResult)
      setState('ready')
      // Descriptive volume/volatility from the SAME stored bars. Uses existing
      // backend indicators; no new analytics engine.
      const analyticsResponse = await apiFetch(
        `${api}/api/terminal/bars/analytics?${new URLSearchParams({ symbol, interval }).toString()}`,
        { credentials: 'include' },
      )
      if (analyticsResponse.ok) setAnalytics(await analyticsResponse.json() as Analytics)
      else setAnalytics(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OHLCV ingestion failed')
      setResult(null)
      setState('error')
    }
  }, [api, marketGroup, symbol, interval])

  const changeMarket = (group: string) => {
    setMarketGroup(group)
    setSymbol(SYMBOLS[group][0].value)
    setInterval(group === 'forex' ? '1d' : '1d')
    setResult(null)
    setAnalytics(null)
    setState('idle')
  }

  return (
    <section className="four-market-chart" aria-label="Four-market OHLCV chart">
      <div className="chart-toolbar">
        <label>MARKET
          <select aria-label="Chart market" value={marketGroup} onChange={e => changeMarket(e.target.value)}>
            {groups.map(group => <option key={group} value={group}>{TITLES[group] || group.toUpperCase()}</option>)}
          </select>
        </label>
        <label>INSTRUMENT
          <select aria-label="Chart instrument" value={symbol} onChange={e => setSymbol(e.target.value)}>
            {(SYMBOLS[marketGroup] || []).map(item => (
              <option key={item.value} value={item.value}>{item.value} · {item.venue}</option>
            ))}
          </select>
        </label>
        <label>INTERVAL
          <select aria-label="Chart interval" value={interval} onChange={e => setInterval(e.target.value)}>
            {supportedIntervals.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <button type="button" className="soft-btn" onClick={() => void load()} disabled={state === 'loading'}>
          {state === 'loading' ? 'FETCHING…' : 'LOAD CANDLES'}
        </button>
      </div>

      {intervals[marketGroup] && (
        <p className="research-note">
          SOURCE {intervals[marketGroup].source} · SUPPORTED {supportedIntervals.join(' / ')} ·
          {intervals[marketGroup].exchange_timezone
            ? ` EXCHANGE TZ ${intervals[marketGroup].exchange_timezone}`
            : ' NO EXCHANGE SESSION (fixing / 24-7)'}
        </p>
      )}

      {state === 'error' && <p className="news-error" role="alert">{error}</p>}
      {state === 'idle' && !result && (
        <p className="research-note">Select a market and instrument, then load historical candles.</p>
      )}

      {result && (
        <>
          <div className="chart-provenance" role="status">
            <span className="quote-badge q-historical">{result.status_label}</span>
            <span>{result.observation_count} CANDLES</span>
            <span>SOURCE {result.source}</span>
            <span>{result.interval}</span>
            <span>{result.first_timestamp} → {result.last_timestamp}</span>
            <span>RETRIEVED {result.retrieved_at}</span>
            {result.exchange_timezone && <span>EXCHANGE TZ {result.exchange_timezone}</span>}
            <span>BROKER {String(result.execution.broker_execution).toUpperCase()}</span>
            <span>REAL MONEY {String(result.execution.real_money).toUpperCase()}</span>
          </div>
          {analytics && (
            <div className="chart-analytics" data-testid="chart-analytics">
              <span>OBSERVATIONS {analytics.observation_count}</span>
              <span>REALIZED VOL {analytics.realized_volatility?.per_observation?.toFixed(6) ?? '—'}</span>
              <span>AVG VOLUME {analytics.average_volume?.toFixed(2) ?? '—'}</span>
              <span>MAX VOLUME {analytics.max_volume?.toFixed(2) ?? '—'}</span>
              <small>Descriptive statistics only; not a forecast or trading signal.</small>
            </div>
          )}
          <div className="chart-host" data-testid="four-market-chart-host">
            <PriceChart bars={result.bars} interval={result.interval} retrievedAt={result.retrieved_at} />
          </div>
          {result.warnings.length > 0 && (
            <ul className="chart-warnings">
              {result.warnings.map(item => <li key={item}>{item}</li>)}
            </ul>
          )}
          <p className="research-note">
            Historical observations with per-candle source and retrieval metadata. Not a live quote,
            trading signal or executable price. Volume=0 means the provider did not supply volume.
          </p>
        </>
      )}
    </section>
  )
}
