import { useMemo, useState } from 'react'

export type CoverageRow = {
  symbol: string
  interval: string
  observation_count: number
  sources: string[]
  statuses: string[]
  last_timestamp: string | null
}

type Props = {
  coverage: CoverageRow[]
  loading: boolean
  error: string | null
  onLoad: () => void
  dataNote?: string
}

const HISTORICAL_NOTICE = 'HISTORICAL OBSERVATIONS — STORED RESEARCH DATA ONLY. NOT LIVE MARKET DATA, PRICE PERFORMANCE, LIQUIDITY OR CURRENT MARKET ACTIVITY.'

function intensity(count: number): 'none' | 'low' | 'medium' | 'high' {
  if (count <= 0) return 'none'
  if (count < 10) return 'low'
  if (count < 100) return 'medium'
  return 'high'
}

/** Search/filter view over stored research observations. */
export function ObservationScreener({ coverage, loading, error, onLoad, dataNote }: Props) {
  const [query, setQuery] = useState('')
  const [timeframe, setTimeframe] = useState('ALL')
  const [minimum, setMinimum] = useState('0')

  const timeframes = useMemo(
    () => ['ALL', ...Array.from(new Set(coverage.map(row => row.interval))).sort()],
    [coverage],
  )

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const floor = Math.max(0, Number.parseInt(minimum, 10) || 0)
    return coverage
      .filter(row => !needle || row.symbol.toLowerCase().includes(needle))
      .filter(row => timeframe === 'ALL' || row.interval === timeframe)
      .filter(row => row.observation_count >= floor)
      .sort((a, b) => b.observation_count - a.observation_count || a.symbol.localeCompare(b.symbol))
  }, [coverage, query, timeframe, minimum])

  return (
    <section className="coverage-tool" aria-label="Research observation screener">
      <div className="side-label">OBSERVATION SCREENER <span>{rows.length} MATCHES</span></div>
      <small className="research-note">{HISTORICAL_NOTICE}</small>
      <div className="screener-controls">
        <label htmlFor="screener-symbol">SYMBOL CONTAINS</label>
        <input id="screener-symbol" aria-label="Filter by symbol" placeholder="e.g. AAPL"
          value={query} onChange={event => setQuery(event.target.value)} />
        <label htmlFor="screener-timeframe">TIMEFRAME</label>
        <select id="screener-timeframe" aria-label="Filter by timeframe" value={timeframe}
          onChange={event => setTimeframe(event.target.value)}>
          {timeframes.map(value => <option key={value} value={value}>{value}</option>)}
        </select>
        <label htmlFor="screener-minimum">MIN OBSERVATIONS</label>
        <input id="screener-minimum" aria-label="Minimum observation count" type="number" min="0" step="1"
          value={minimum} onChange={event => setMinimum(event.target.value)} />
        <button type="button" className="soft-btn research-run" onClick={onLoad} disabled={loading}>
          {loading ? 'LOADING COVERAGE…' : 'LOAD STORED OBSERVATIONS'}
        </button>
      </div>
      {error && <p className="news-error" role="alert">{error}</p>}
      {loading && <small role="status">LOADING STORED OBSERVATIONS…</small>}
      {!loading && !error && rows.length === 0 && (
        <small className="research-note">No stored observations match these filters. This is not a live market screener.</small>
      )}
      {!loading && rows.length > 0 && (
        <div className="screener-results">
          {rows.map(row => (
            <div className="aligned-row" key={`${row.symbol}-${row.interval}`}>
              <b>{row.symbol}</b>
              <span>{row.interval}</span>
              <span>{row.observation_count} observations</span>
              <small>{row.sources.join(', ') || 'unknown source'} · {row.statuses.join(', ') || 'unlabelled'} · last {row.last_timestamp || '—'}</small>
            </div>
          ))}
        </div>
      )}
      {dataNote && <small className="research-note">{dataNote}</small>}
    </section>
  )
}

/** Symbol x timeframe intensity grid over stored observation counts only. */
export function CoverageHeatmap({ coverage, loading, error, onLoad, dataNote }: Props) {
  const symbols = useMemo(
    () => Array.from(new Set(coverage.map(row => row.symbol))).sort(),
    [coverage],
  )
  const timeframes = useMemo(
    () => Array.from(new Set(coverage.map(row => row.interval))).sort(),
    [coverage],
  )
  const counts = useMemo(() => {
    const table = new Map<string, number>()
    for (const row of coverage) table.set(`${row.symbol}|${row.interval}`, row.observation_count)
    return table
  }, [coverage])

  return (
    <section className="coverage-tool" aria-label="Stored observation coverage heatmap">
      <div className="side-label">COVERAGE HEATMAP <span>STORED OBSERVATIONS</span></div>
      <small className="research-note">{HISTORICAL_NOTICE}</small>
      <button type="button" className="soft-btn research-run" onClick={onLoad} disabled={loading}>
        {loading ? 'LOADING COVERAGE…' : 'LOAD COVERAGE'}
      </button>
      {error && <p className="news-error" role="alert">{error}</p>}
      {loading && <small role="status">LOADING COVERAGE…</small>}
      {!loading && !error && symbols.length === 0 && (
        <small className="research-note">No stored coverage yet. Cells appear only when research observations exist.</small>
      )}
      {!loading && symbols.length > 0 && (
        <div className="heatmap-scroll">
          <table className="heatmap-table">
            <thead><tr><th scope="col">SYMBOL</th>{timeframes.map(tf => <th scope="col" key={tf}>{tf}</th>)}</tr></thead>
            <tbody>
              {symbols.map(symbol => (
                <tr key={symbol}>
                  <th scope="row">{symbol}</th>
                  {timeframes.map(tf => {
                    const count = counts.get(`${symbol}|${tf}`) || 0
                    const level = intensity(count)
                    return (
                      <td key={tf} className={`heat-cell heat-${level}`}
                        aria-label={`${symbol} ${tf}: ${count} stored observations, ${level} coverage`}
                        title={`${count} stored observations`}>
                        {count || '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="heatmap-legend" aria-label="Coverage intensity legend">
        <span>COVERAGE INTENSITY (OBSERVATIONS STORED)</span>
        <span className="heat-legend-item heat-none">none</span>
        <span className="heat-legend-item heat-low">1–9</span>
        <span className="heat-legend-item heat-medium">10–99</span>
        <span className="heat-legend-item heat-high">100+</span>
      </div>
      {dataNote && <small className="research-note">{dataNote}</small>}
    </section>
  )
}

export default function CoverageTools(props: Props & { view: 'screener' | 'heatmap' }) {
  const { view, ...rest } = props
  return view === 'screener' ? <ObservationScreener {...rest} /> : <CoverageHeatmap {...rest} />
}
