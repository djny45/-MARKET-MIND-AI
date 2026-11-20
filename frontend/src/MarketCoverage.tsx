import { useMemo, useState } from 'react'

type Coverage = {
  symbol: string
  interval: string
  observation_count: number
  sources?: string[]
  statuses?: string[]
  first_timestamp?: string | null
  last_timestamp?: string | null
}

type Props = {
  coverage: Coverage[]
  onAnalyze: (symbol: string, interval: string) => void
}

export default function MarketCoverage({ coverage, onAnalyze }: Props) {
  const [query, setQuery] = useState('')
  const [interval, setInterval] = useState('ALL')
  const [minimum, setMinimum] = useState('0')
  const filtered = useMemo(() => coverage.filter(item =>
    item.symbol.toLowerCase().includes(query.trim().toLowerCase()) &&
    (interval === 'ALL' || item.interval === interval) &&
    item.observation_count >= Number(minimum)
  ).sort((a, b) => b.observation_count - a.observation_count), [coverage, query, interval, minimum])
  const intervals = useMemo(() => [...new Set(coverage.map(item => item.interval))].sort(), [coverage])
  const max = Math.max(1, ...coverage.map(item => item.observation_count))
  const intensity = (count: number) => count / max >= .75 ? 'high' : count / max >= .35 ? 'medium' : 'low'

  return <section className="market-coverage-workbench">
    <div className="coverage-workbench-heading">
      <div><b>MARKET COVERAGE HEATMAP</b><small>Stored OHLCV observation density · not price performance</small></div>
      <span>{coverage.length} SYMBOL / TIMEFRAME CELLS</span>
    </div>
    {coverage.length === 0 ? <div className="overview-empty">No stored observations yet. Import historical OHLCV data in Research to populate the coverage heatmap and screener.</div> :
      <div className="coverage-heatmap" role="list" aria-label="Stored market data coverage heatmap">
        {coverage.slice(0, 60).map(item => <button type="button" role="listitem" className={"coverage-heat-cell " + intensity(item.observation_count)} key={item.symbol + '-' + item.interval} onClick={() => onAnalyze(item.symbol, item.interval)} title={item.symbol + ' ' + item.interval + ': ' + item.observation_count + ' stored observations'}>
          <b>{item.symbol}</b><span>{item.interval}</span><strong>{item.observation_count.toLocaleString()}</strong>
        </button>)}
      </div>}
    <div className="coverage-workbench-heading screener-heading">
      <div><b>LOCAL DATA SCREENER</b><small>Filter instruments by stored coverage; no live quote or return ranking</small></div>
      <span>{filtered.length} MATCHES</span>
    </div>
    <div className="coverage-screener-filters">
      <input aria-label="Filter symbols" placeholder="Filter symbol…" value={query} onChange={event => setQuery(event.target.value)} />
      <select aria-label="Filter timeframe" value={interval} onChange={event => setInterval(event.target.value)}>
        <option value="ALL">ALL TIMEFRAMES</option>
        {intervals.map(value => <option key={value} value={value}>{value}</option>)}
      </select>
      <select aria-label="Minimum observations" value={minimum} onChange={event => setMinimum(event.target.value)}>
        <option value="0">ANY OBSERVATION COUNT</option><option value="10">10+ OBSERVATIONS</option><option value="50">50+ OBSERVATIONS</option><option value="100">100+ OBSERVATIONS</option><option value="500">500+ OBSERVATIONS</option>
      </select>
    </div>
    <div className="coverage-screener-table">
      <div className="coverage-screener-row coverage-screener-header"><span>INSTRUMENT</span><span>TIMEFRAME</span><span>OBSERVATIONS</span><span>DATA STATUS</span><span>ACTION</span></div>
      {filtered.slice(0, 100).map(item => <div className="coverage-screener-row" key={item.symbol + '-' + item.interval}>
        <b>{item.symbol}</b><span>{item.interval}</span><span>{item.observation_count.toLocaleString()}</span><span>{item.statuses?.join(', ') || 'UNSPECIFIED'}</span>
        <button className="soft-btn" onClick={() => onAnalyze(item.symbol, item.interval)}>ANALYZE</button>
      </div>)}
      {filtered.length === 0 && <div className="overview-empty">No rows match these filters.</div>}
    </div>
    <small className="coverage-data-note">Coverage intensity is normalized to the largest observation count in this result. It does not represent returns, momentum, liquidity, or current market conditions.</small>
  </section>
}
