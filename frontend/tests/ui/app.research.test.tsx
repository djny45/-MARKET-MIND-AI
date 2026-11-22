import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { bodyOf, clickTab, json, setupApp } from './helpers'

const historyBars = [
  { timestamp: '2026-01-01T00:00:00Z', open: 10, high: 12, low: 9, close: 11, volume: 100, source: 'local-csv', status: 'historical' },
  { timestamp: '2026-01-02T00:00:00Z', open: 11, high: 13, low: 10, close: 12, volume: 120, source: 'local-csv', status: 'historical' },
]

const deepReport = {
  symbol: 'BTCUSD',
  dashboard: {
    data_quality: { timeframes_checked: 4, timeframes_with_issues: 1 },
    historical_price_clusters: { confirmed_swing_high_cluster_count: 1, confirmed_swing_low_cluster_count: 0 },
    timeframes: [{ interval: '1h', status: 'available', moving_average_regime: 'bullish', rsi14: 55, atr14: 2 }],
    market_breadth_latest: { advancing: 3, declining: 2 },
  },
  timeframes: {
    '1h': {
      seasonality: {
        status: 'status_ok', return_observations: 10, skipped_observations: 0,
        by_weekday: [{ bucket: 'Monday', sample_count: 5, mean_return_pct: 0.2, median_return_pct: 0.1 }],
        by_calendar_month: [{ bucket: 'January', sample_count: 5, mean_return_pct: 0.3, median_return_pct: 0.2 }],
      },
      historical_price_clusters: {
        clusters: {
          historical_swing_high: [{ mean_price: 100, lower_price: 99, upper_price: 101, touch_count: 3, pivot_timestamps: ['2026-01-01T00:00:00Z', null] }],
          historical_swing_low: [],
        },
      },
    },
  },
}

describe('App / research workbench: CSV import', () => {
  it('IMPORT HISTORICAL CSV is disabled until text and source exist, then posts and refreshes derived data', async () => {
    const { user, calls } = setupApp({
      'POST /api/market-data/import-csv': (_url, init) => {
        const payload = bodyOf(init)
        expect(payload.symbol).toBe('BTCUSD')
        expect(payload.csv_text).toContain('timestamp,open,high,low,close,volume')
        return json({ stored: 2, symbol: 'BTCUSD', interval: '1h', source: 'local-csv' })
      },
      'GET /api/market-data/history': () => json({ bars: historyBars, source: 'local-csv', status: 'historical', retrieved_at: '2026-01-03T00:00:00Z' }),
      'GET /api/research/timeline': () => json({ events: historyBars.map((bar, index) => ({ index, ...bar, close_change_pct: 10 })) }),
    })
    await clickTab(user, 'RESEARCH')
    const importButton = await screen.findByRole('button', { name: 'IMPORT HISTORICAL CSV' })
    expect(importButton).toBeEnabled()
    expect(screen.getByRole('button', { name: 'CALCULATE FROM LOADED OHLCV' })).toBeDisabled()

    await user.click(importButton)
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/market-data/import-csv'))).toBe(true))
    expect(await screen.findByText(/IMPORTED 2 BARS · BTCUSD · 1h · local-csv/)).toBeInTheDocument()
    expect(calls.some(call => call.url.includes('/api/market-data/history?symbol=BTCUSD&interval=1h'))).toBe(true)
    expect(calls.some(call => call.url.includes('/api/research/timeline'))).toBe(true)
    expect(screen.getByRole('button', { name: 'CALCULATE FROM LOADED OHLCV' })).toBeEnabled()
    expect(screen.getByText(/Uses 2 loaded historical bars/)).toBeInTheDocument()
  })

  it('surfaces CSV import API errors', async () => {
    const { user } = setupApp({ 'POST /api/market-data/import-csv': () => json({ detail: 'bad csv' }, 422) })
    await clickTab(user, 'RESEARCH')
    await user.click(await screen.findByRole('button', { name: 'IMPORT HISTORICAL CSV' }))
    expect(await screen.findByText('bad csv')).toBeInTheDocument()
  })

  it('validates file selection (extension, size, empty content)', async () => {
    const { user } = setupApp()
    await clickTab(user, 'RESEARCH')
    const fileInput = await screen.findByLabelText('Select historical CSV file')

    const tooBig = new File(['x'], 'huge.csv', { type: 'text/csv' })
    Object.defineProperty(tooBig, 'size', { value: 2_000_001 })
    await user.upload(fileInput, tooBig)
    expect(await screen.findByText('FILE TOO LARGE · MAXIMUM 2 MB')).toBeInTheDocument()

    await user.upload(fileInput, new File(['a,b'], 'notes.txt', { type: 'text/csv' }))
    expect(await screen.findByText('PLEASE SELECT A .CSV FILE')).toBeInTheDocument()

    await user.upload(fileInput, new File(['   '], 'empty.csv', { type: 'text/csv' }))
    expect(await screen.findByText(/Selected CSV file is empty/)).toBeInTheDocument()

    await user.upload(fileInput, new File(['timestamp,open,high,low,close,volume\nx'], 'prices.csv', { type: 'text/csv' }))
    expect(await screen.findByText(/LOADED prices.csv/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Historical OHLCV CSV' })).toHaveValue('timestamp,open,high,low,close,volume\nx')
  })
})

describe('App / research workbench: offline benchmark', () => {
  it('rejects an out-of-range threshold locally and an oversized baseline file', async () => {
    const { user } = setupApp()
    await clickTab(user, 'RESEARCH')
    const threshold = await screen.findByRole('spinbutton', { name: 'Regression threshold' })
    await user.clear(threshold)
    await user.type(threshold, '2')
    await user.click(screen.getByRole('button', { name: 'RUN OFFLINE BENCHMARK' }))
    expect(await screen.findByText('Regression threshold must be between 0 and 1')).toBeInTheDocument()

    const big = new File(['{}'], 'baseline.json', { type: 'application/json' })
    Object.defineProperty(big, 'size', { value: 2_000_001 })
    await user.upload(screen.getByLabelText('Upload previous benchmark JSON'), big)
    await user.clear(threshold)
    await user.type(threshold, '0.05')
    await user.click(screen.getByRole('button', { name: 'RUN OFFLINE BENCHMARK' }))
    expect(await screen.findByText('Baseline JSON exceeds 2 MB')).toBeInTheDocument()
  })

  it('renders a real benchmark report including regression summary and download action', async () => {
    const { user, calls } = setupApp({
      'POST /api/research/benchmark': (_url, init) => {
        const payload = bodyOf(init)
        expect(payload.regression_threshold).toBe(0.05)
        expect(payload.cases).toHaveLength(2)
        return json({
          benchmark_id: 'bm-42', case_count: 2,
          aggregate_metrics: { claim_coverage: { mean: 0.9 }, source_integrity: { mean: null } },
          regression_summary: { status: 'no_regression', items: [] },
        })
      },
    })
    await clickTab(user, 'RESEARCH')
    await user.click(await screen.findByRole('button', { name: 'RUN OFFLINE BENCHMARK' }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/research/benchmark'))).toBe(true))
    expect(await screen.findByText('BENCHMARK bm-42')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('90.0%')).toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText('NO REGRESSION')).toBeInTheDocument()

    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await user.click(screen.getByRole('button', { name: 'DOWNLOAD BENCHMARK JSON' }))
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    expect(screen.getByText(/Structural traceability only/)).toBeInTheDocument()
  })

  it('shows benchmark API errors', async () => {
    const { user } = setupApp({ 'POST /api/research/benchmark': () => json({ detail: 'benchmark unavailable' }, 500) })
    await clickTab(user, 'RESEARCH')
    await user.click(await screen.findByRole('button', { name: 'RUN OFFLINE BENCHMARK' }))
    expect(await screen.findByText('benchmark unavailable')).toBeInTheDocument()
  })
})

describe('App / research workbench: deep research, audit and exports', () => {
  it('RUN DEEP RESEARCH sends the chosen symbol/timeframes/compare list and renders the report', async () => {
    const { user, calls } = setupApp({
      'GET /api/research/deep': url => {
        expect(url.searchParams.get('symbol')).toBe('BTCUSD')
        expect(url.searchParams.get('intervals')).toBe('1h')
        expect(url.searchParams.get('compare_symbols')).toBe('ETHUSD')
        return json(deepReport)
      },
    })
    await clickTab(user, 'RESEARCH')
    const symbolInput = await screen.findByRole('textbox', { name: 'Research symbol' })
    await user.clear(symbolInput)
    await user.type(symbolInput, 'BTCUSD')
    await user.clear(screen.getByRole('textbox', { name: 'Comparison symbols' }))
    await user.type(screen.getByRole('textbox', { name: 'Comparison symbols' }), 'ETHUSD')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Research timeframes' }), '1h')
    await user.click(screen.getByRole('button', { name: 'RUN DEEP RESEARCH' }))
    await waitFor(() => expect(calls.some(call => call.url.includes('/api/research/deep?'))).toBe(true))
    expect(await screen.findByText('HISTORICAL SEASONALITY · 1h')).toBeInTheDocument()
    expect(screen.getByText('Monday')).toBeInTheDocument()
    expect(await screen.findByText('January')).toBeInTheDocument()
    expect(screen.getByText('bullish')).toBeInTheDocument()
    expect(screen.getByText(/3 \/ 2/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'OPEN FULL RESEARCH JSON' })).toBeInTheDocument()
  })

  it('deep research exposes a busy state and reports API failure', async () => {
    let gate: Promise<Response> = Promise.resolve(json(deepReport))
    const { user } = setupApp({ 'GET /api/research/deep': () => gate })
    await clickTab(user, 'RESEARCH')
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(await screen.findByRole('button', { name: 'RUN DEEP RESEARCH' }))
    expect(screen.getByRole('button', { name: 'ANALYZING…' })).toBeDisabled()
    resolve(json({ detail: 'research denied' }, 500))
    expect(await screen.findByText('research denied')).toBeInTheDocument()
  })

  it('audit and lineage loads both endpoints and shows stored provenance', async () => {
    const { calls, user } = setupApp({
      'GET /api/market-data/lineage': () => json({ symbol: 'BTCUSD', interval: '1h', observation_count: 10, lineage: [{ source: 'local-csv', status: 'historical', observation_count: 10, first_timestamp: '2026-01-01T00:00:00Z', last_timestamp: '2026-01-02T00:00:00Z', latest_retrieval: '2026-01-03T00:00:00Z' }] }),
      'GET /api/audit/events': () => json({ count: 1, events: [{ id: 7, event_type: 'batch_write', source: 'local-csv', observation_count: 10, occurred_at: '2026-01-03T00:00:00Z' }] }),
    })
    await clickTab(user, 'RESEARCH')
    await user.click(await screen.findByRole('button', { name: 'VIEW INGESTION AUDIT & LINEAGE' }))
    await waitFor(() => expect(calls.some(call => call.url.includes('/api/market-data/lineage'))).toBe(true))
    expect(calls.some(call => call.url.includes('/api/audit/events'))).toBe(true)
    expect(await screen.findByText(/STORED DATA LINEAGE · BTCUSD · 1h/)).toBeInTheDocument()
    expect(screen.getByText(/RECENT INGESTION EVENTS · 1/)).toBeInTheDocument()
    expect(screen.getByText(/#7 · batch_write/)).toBeInTheDocument()
  })

  it('COMPARE TWO EXPORTS posts exactly two chosen JSON files and renders the diff', async () => {
    const { calls, user } = setupApp({
      'POST /api/research/compare-exports': (_url, init) => {
        const payload = bodyOf(init)
        expect(Object.keys(payload)).toEqual(['before', 'after'])
        return json({
          counts: { added: 1, removed: 0, changed: 2, unchanged: 3 },
          integrity_validation: { before: { valid: true }, after: { valid: false, reason: 'digest mismatch' } },
          provenance_changed_fields: ['source'],
          changed: [{ timestamp: '2026-01-01T00:00:00Z', source: 'csv', fields: ['close'] }],
        })
      },
    })
    await clickTab(user, 'RESEARCH')
    const compare = await screen.findByRole('button', { name: 'COMPARE TWO EXPORTS' })
    expect(compare).toBeDisabled()
    const input = screen.getByLabelText('Select two historical research JSON exports')
    await user.upload(input, [
      new File(['{"a":1}'], 'before.json', { type: 'application/json' }),
      new File(['{"a":2}'], 'after.json', { type: 'application/json' }),
    ])
    expect(screen.getByRole('button', { name: 'COMPARE TWO EXPORTS' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'COMPARE TWO EXPORTS' }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/research/compare-exports'))).toBe(true))
    expect(await screen.findByText('EXPORT DIFFERENCE REPORT')).toBeInTheDocument()
    expect(screen.getByText('1 / 0')).toBeInTheDocument()
    expect(screen.getByText('VALID / digest mismatch')).toBeInTheDocument()
  })

  it('rejects an export file larger than 10 MB', async () => {
    const { user } = setupApp()
    await clickTab(user, 'RESEARCH')
    const big = new File(['{}'], 'huge.json', { type: 'application/json' })
    Object.defineProperty(big, 'size', { value: 10_000_001 })
    await user.upload(screen.getByLabelText('Select two historical research JSON exports'), [big, new File(['{}'], 'small.json', { type: 'application/json' })])
    await user.click(await screen.findByRole('button', { name: 'COMPARE TWO EXPORTS' }))
    expect(await screen.findByText(/huge.json exceeds the 10 MB limit/)).toBeInTheDocument()
  })
})

describe('App / research workbench: historical indicators and inspectors', () => {
  async function loadBarsFirst(routes: Record<string, any> = {}) {
    const setup = setupApp({
      'POST /api/market-data/import-csv': () => json({ stored: 2, symbol: 'BTCUSD', interval: '1h', source: 'local-csv' }),
      'GET /api/market-data/history': () => json({ bars: historyBars, source: 'local-csv', status: 'historical' }),
      ...routes,
    })
    await clickTab(setup.user, 'RESEARCH')
    await setup.user.click(await screen.findByRole('button', { name: 'IMPORT HISTORICAL CSV' }))
    await screen.findByText(/IMPORTED 2 BARS/)
    return setup
  }

  it('VOLUME and LIQUIDITY calculations post the loaded OHLCV series and render results', async () => {
    const { user, calls } = await loadBarsFirst({
      'POST /api/indicators/volume': (_url: URL, init?: RequestInit) => {
        const payload = bodyOf(init)
        expect(payload.close).toEqual([11, 12])
        const series = new Array(12).fill(0)
        return json({ obv: series, adl: series, cmf: series, mfi: series, vwap: series, relative_volume: series, volume_oscillator: series, volume_rate_of_change: series, force_index: series, ease_of_movement: series, vpt: series, chaikin_oscillator: series })
      },
      'POST /api/indicators/liquidity-profile': () => json({
        poc: 100, value_area_high: 105, value_area_low: 95, total_volume: 1000, value_area_volume_pct_actual: 70,
        profile: [{ price_mid: 100, volume: 100, share_pct: 50 }, { price_mid: 105, volume: 100, share_pct: 50 }],
        metadata: { classification: 'balanced' },
      }),
    })
    await user.click(screen.getByRole('button', { name: 'CALCULATE FROM LOADED OHLCV' }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/indicators/volume'))).toBe(true))
    expect(await screen.findByText('On-Balance Volume')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'CALCULATE PROFILE' }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/indicators/liquidity-profile'))).toBe(true))
    expect(await screen.findByText(/POINT OF CONTROL/)).toBeInTheDocument()
    expect(screen.getByText(/balanced/)).toBeInTheDocument()
  })

  it('indicator buttons are disabled with fewer than two stored bars', async () => {
    const { user } = setupApp()
    await clickTab(user, 'RESEARCH')
    expect(await screen.findByRole('button', { name: 'CALCULATE FROM LOADED OHLCV' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'CALCULATE PROFILE' })).toBeDisabled()
  })

  it('cluster selection, timeline inspection and clear actions all work', async () => {
    const { user, calls } = setupApp({
      'GET /api/research/deep': () => json(deepReport),
      'GET /api/research/timeline': () => json({ events: historyBars.map((bar, index) => ({ index, ...bar, close_change_pct: 10, indicator_context: { sma20: 11, rsi14: 55, macd: 0.1, macd_signal: 0.05, macd_histogram: 0.05 } })) }),
    })
    await clickTab(user, 'RESEARCH')
    await user.click(await screen.findByRole('button', { name: 'RUN DEEP RESEARCH' }))
    await screen.findByText('HISTORICAL SEASONALITY · 1h')

    const cluster = await screen.findByRole('button', { name: /100.*3 pivots/ })
    await user.click(cluster)
    expect(await screen.findByText('SELECTED HISTORICAL CLUSTER')).toBeInTheDocument()
    expect(screen.getByText(/Horizontal chart overlay is a historical reference only/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'CLEAR OVERLAY' }))
    expect(screen.queryByText('SELECTED HISTORICAL CLUSTER')).not.toBeInTheDocument()

    await waitFor(() => expect(calls.some(call => call.url.includes('/api/research/timeline'))).toBe(true))
    const event = (await screen.findAllByRole('button', { name: /2026-01-0[12]T00:00:00Z/ }))[0]
    await user.click(event)
    expect(await screen.findByText('SELECTED OBSERVATION')).toBeInTheDocument()
    expect(screen.getByText(/HISTORICAL INDICATOR CONTEXT/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'CLEAR' }))
    expect(screen.queryByText('SELECTED OBSERVATION')).not.toBeInTheDocument()
  })
})
