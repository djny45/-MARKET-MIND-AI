import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const NOW = '2026-11-26T12:00:00Z'

const bars = [
  { timestamp: '2026-11-24T14:30:00Z', open: 100, high: 103, low: 99, close: 102, volume: 1000 },
  { timestamp: '2026-11-25T14:30:00Z', open: 102, high: 105, low: 101, close: 104, volume: 1200 },
]

function ingestion(overrides: Record<string, unknown> = {}) {
  return {
    mode: 'four_market_historical_ingestion',
    symbol: 'AAPL', market_group: 'us', venue: 'NASDAQ', interval: '1d',
    source: 'yahoo-us-equities', status: 'historical', status_label: 'HISTORICAL',
    retrieved_at: NOW, observation_count: 2,
    first_timestamp: '2026-11-24T14:30:00Z', last_timestamp: '2026-11-25T14:30:00Z',
    exchange_timezone: 'America/New_York',
    warnings: ['Historical research only; not a live quote.'],
    bars,
    storage: { inserted: 2 },
    execution: { paper_trading: false, broker_execution: false, real_money: false },
    ...overrides,
  }
}

function intervals() {
  return {
    intervals: [
      { market_group: 'us', source: 'yahoo-us-equities',
        supported_intervals: ['15m', '1h', '4h', '1d'],
        exchange_timezone: 'America/New_York', note: 'Yahoo chart endpoint.' },
      { market_group: 'india', source: 'yahoo-india-nse-bse',
        supported_intervals: ['15m', '1h', '4h', '1d'],
        exchange_timezone: 'Asia/Kolkata', note: 'Yahoo chart endpoint.' },
      { market_group: 'forex', source: 'ecb-reference-rates',
        supported_intervals: ['1d'], exchange_timezone: null, note: 'ECB publishes one fixing.' },
      { market_group: 'crypto', source: 'coingecko-public',
        supported_intervals: ['15m', '1h', '4h', '1d'],
        exchange_timezone: null, note: 'CoinGecko OHLC.' },
    ],
    supported: ['15m', '1h', '4h', '1d'],
  }
}


function board() {
  return {
    generated_at: NOW, mode: 'four_market_research_terminal',
    market_groups: ['us', 'india', 'forex', 'crypto'], markets: [],
    totals: { markets: 0, quotes: 0, usable: 0, unavailable: 0, stale: 0 },
    legend: { labels: [], stale_rule: '' },
    providers: { note: '' }, attested_sources: [],
    execution: { paper_trading: false, broker_execution: false, real_money: false },
  }
}

const BOARD = { 'GET /api/terminal/four-market': () => json(board()) }

describe('Four-market OHLCV chart', () => {
  it('loads candles with full provenance into the chart', async () => {
    const { user, calls } = setupApp({
      ...BOARD,
      'GET /api/terminal/bars/intervals': () => json(intervals()),
      'POST /api/terminal/bars/ingest': () => json(ingestion()),
    })
    await clickTab(user, 'FOUR MARKETS')
    const chart = await screen.findByRole('region', { name: 'Four-market OHLCV chart' })

    await user.click(within(chart).getByRole('button', { name: 'LOAD CANDLES' }))

    expect(await within(chart).findByTestId('four-market-chart-host')).toBeInTheDocument()
    expect(within(chart).getByText(/2 CANDLES/)).toBeInTheDocument()
    const provenance = within(chart).getByRole('status')
    expect(within(provenance).getByText(/SOURCE yahoo-us-equities/)).toBeInTheDocument()
    expect(within(provenance).getByText(/EXCHANGE TZ America\/New_York/)).toBeInTheDocument()
    expect(within(provenance).getByText(/BROKER FALSE/)).toBeInTheDocument()
    expect(within(provenance).getByText(/REAL MONEY FALSE/)).toBeInTheDocument()
    expect(calls.some(c => c.url.includes('/api/terminal/bars/ingest') && c.method === 'POST')).toBe(true)
  })

  it('displays HISTORICAL status and source warnings', async () => {
    const { user } = setupApp({
      ...BOARD,
      'GET /api/terminal/bars/intervals': () => json(intervals()),
      'POST /api/terminal/bars/ingest': () => json(ingestion()),
    })
    await clickTab(user, 'FOUR MARKETS')
    const chart = await screen.findByRole('region', { name: 'Four-market OHLCV chart' })
    await user.click(within(chart).getByRole('button', { name: 'LOAD CANDLES' }))

    expect(await within(chart).findByText('HISTORICAL')).toBeInTheDocument()
    expect(within(chart).getByText(/Historical research only; not a live quote/)).toBeInTheDocument()
  })

  it('shows an error when no candles are returned', async () => {
    const { user } = setupApp({
      ...BOARD,
      'GET /api/terminal/bars/intervals': () => json(intervals()),
      'POST /api/terminal/bars/ingest': () => json({ detail: 'CoinGecko returned no usable OHLC candles' }, 400),
    })
    await clickTab(user, 'FOUR MARKETS')
    const chart = await screen.findByRole('region', { name: 'Four-market OHLCV chart' })
    await user.click(within(chart).getByRole('button', { name: 'LOAD CANDLES' }))

    expect(await within(chart).findByRole('alert')).toHaveTextContent('no usable OHLC candles')
    expect(within(chart).queryByTestId('four-market-chart-host')).not.toBeInTheDocument()
  })

  it('restricts forex to a daily interval', async () => {
    const { user } = setupApp({
      ...BOARD,
      'GET /api/terminal/bars/intervals': () => json(intervals()),
      'POST /api/terminal/bars/ingest': () => json(ingestion({ market_group: 'forex', interval: '1d' })),
    })
    await clickTab(user, 'FOUR MARKETS')
    const chart = await screen.findByRole('region', { name: 'Four-market OHLCV chart' })
    await user.selectOptions(within(chart).getByLabelText('Chart market'), 'forex')

    const options = within(chart).getByLabelText('Chart interval').querySelectorAll('option')
    expect(Array.from(options).map(o => o.textContent)).toEqual(['1d'])
    expect(within(chart).getByText(/NO EXCHANGE SESSION/)).toBeInTheDocument()
  })

  it('sends the selected market, symbol and interval to the ingest API', async () => {
    const { user, calls } = setupApp({
      ...BOARD,
      'GET /api/terminal/bars/intervals': () => json(intervals()),
      'POST /api/terminal/bars/ingest': () => json(ingestion()),
    })
    await clickTab(user, 'FOUR MARKETS')
    const chart = await screen.findByRole('region', { name: 'Four-market OHLCV chart' })
    await user.selectOptions(within(chart).getByLabelText('Chart market'), 'india')
    await user.selectOptions(within(chart).getByLabelText('Chart instrument'), 'RELIANCE')
    await user.selectOptions(within(chart).getByLabelText('Chart interval'), '1h')
    await user.click(within(chart).getByRole('button', { name: 'LOAD CANDLES' }))

    const call = calls.find(c => c.url.includes('/api/terminal/bars/ingest'))
    expect(call).toBeDefined()
    expect(call!.url).toContain('market_group=india')
    expect(call!.url).toContain('symbol=RELIANCE')
    expect(call!.url).toContain('interval=1h')
  })
})
