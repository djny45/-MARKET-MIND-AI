import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const NOW = '2026-11-26T12:00:00Z'

function quote(overrides: Record<string, unknown> = {}) {
  return {
    symbol: 'AAPL', name: 'Apple Inc.', asset_class: 'equities', market_group: 'us',
    exchange: 'NASDAQ', currency: 'USD', instrument_id: 'us:nasdaq:AAPL',
    last: 200.5, bid: null, ask: null, change_pct: 1.25,
    timestamp: '2026-11-25T20:00:00Z', retrieved_at: NOW,
    status: 'historical', status_label: 'HISTORICAL',
    source: 'yahoo-us-equities', quote_type: 'close', delay_seconds: null,
    reason: null, age_seconds: 57600, stale: false, max_age_seconds: 604800,
    exchange_timezone: 'America/New_York',
    timestamp_exchange_local: '2026-11-25T09:30:00-05:00',
    ...overrides,
  }
}

function unavailableQuote(overrides: Record<string, unknown> = {}) {
  return quote({
    symbol: 'MSFT', name: 'Microsoft Corp.', last: null, change_pct: null,
    status: 'unavailable', status_label: 'UNAVAILABLE',
    reason: 'adapter error (ProviderError); no price is implied',
    age_seconds: 0, stale: false, max_age_seconds: null,
    ...overrides,
  })
}

function market(overrides: Record<string, unknown> = {}) {
  return {
    market_group: 'us',
    market_status: 'fresh',
    headline: 'FRESH',
    requested: 2,
    usable_count: 1,
    unavailable_count: 1,
    stale_count: 0,
    status_counts: { historical: 1, unavailable: 1 },
    coverage_ratio: 0.5,
    adapter: {
      name: 'yahoo-us-equities',
      preferred_status: 'delayed',
      requires_attestation: true,
      licensing_note: 'Community-facing Yahoo chart endpoint; unofficial.',
      limitations: ['Unofficial endpoint.', 'Not execution-grade.'],
    },
    quotes: [quote(), unavailableQuote()],
    ...overrides,
  }
}

function snapshot(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: NOW,
    mode: 'four_market_research_terminal',
    market_groups: ['us', 'india', 'forex', 'crypto'],
    markets: [
      market(),
      market({
        market_group: 'india', market_status: 'unavailable', headline: 'NO USABLE OBSERVATION',
        usable_count: 0, unavailable_count: 1, status_counts: { unavailable: 1 },
        adapter: {
          name: 'yahoo-india-nse-bse', preferred_status: 'delayed', requires_attestation: true,
          licensing_note: 'NSE and BSE data policy applies.', limitations: ['Unofficial coverage.'],
        },
        quotes: [unavailableQuote({
          symbol: 'RELIANCE', name: 'Reliance Industries Ltd.', market_group: 'india',
          exchange: 'NSE', currency: 'INR', source: 'yahoo-india-nse-bse',
          exchange_timezone: 'Asia/Kolkata',
          timestamp_exchange_local: '2026-11-26T09:15:00+05:30',
        })],
      }),
      market({
        market_group: 'forex', market_status: 'fresh', headline: 'FRESH',
        usable_count: 1, unavailable_count: 0, status_counts: { historical: 1 },
        adapter: {
          name: 'ecb-reference-rates', preferred_status: 'historical', requires_attestation: false,
          licensing_note: 'ECB reference rates are informational.', limitations: ['One fixing per day.'],
        },
        quotes: [quote({
          symbol: 'EURUSD', name: 'Euro / US Dollar', market_group: 'forex',
          exchange: 'OTC', currency: 'USD', source: 'ecb-reference-rates',
          quote_type: 'reference', last: 1.1, change_pct: null,
          timestamp: '2026-11-25T00:00:00Z',
          exchange_timezone: null, timestamp_exchange_local: null,
        })],
      }),
      market({
        market_group: 'crypto', market_status: 'stale', headline: 'ALL OBSERVATIONS STALE',
        usable_count: 1, unavailable_count: 0, stale_count: 1, status_counts: { delayed: 1 },
        adapter: {
          name: 'coingecko-public', preferred_status: 'delayed', requires_attestation: true,
          licensing_note: 'CoinGecko public API.', limitations: ['Aggregated cross-venue price.'],
        },
        quotes: [quote({
          symbol: 'BTCUSD', name: 'Bitcoin / US Dollar', market_group: 'crypto',
          exchange: 'Multi-venue', source: 'coingecko-public', quote_type: 'mid',
          last: 95000.5, status: 'delayed', status_label: 'DELAYED',
          age_seconds: 1800, stale: true, max_age_seconds: 900,
          exchange_timezone: null, timestamp_exchange_local: null,
        })],
      }),
    ],
    totals: { markets: 4, quotes: 5, usable: 3, unavailable: 2, stale: 1 },
    legend: {
      labels: [
        { status: 'live', label: 'LIVE', max_age_seconds: 60, meaning: 'Attested near-real-time.' },
        { status: 'delayed', label: 'DELAYED', max_age_seconds: 900, meaning: 'Attested with a known delay.' },
        { status: 'historical', label: 'HISTORICAL', max_age_seconds: 604800, meaning: 'Archived or end-of-day.' },
        { status: 'synthetic', label: 'SYNTHETIC', max_age_seconds: 3600, meaning: 'Development fixture.' },
        { status: 'unavailable', label: 'UNAVAILABLE', max_age_seconds: null, meaning: 'No usable observation.' },
      ],
      stale_rule: 'A quote is stale when its event age exceeds the status threshold.',
    },
    providers: {
      note: 'A source may only claim LIVE or DELAYED when the operator attests it.',
      live_claims_require_attestation: true,
    },
    attested_sources: [],
    execution: { paper_trading: false, broker_execution: false, real_money: false },
    ...overrides,
  }
}

describe('Four-market terminal', () => {
  it('renders one panel per market with adapter attribution', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByRole('heading', { name: /United States · India · Forex · Crypto/i })).toBeInTheDocument()

    for (const label of ['UNITED STATES', 'INDIA · NSE / BSE', 'FOREX · OTC', 'CRYPTOCURRENCY']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
    expect(screen.getAllByText('yahoo-us-equities').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ecb-reference-rates').length).toBeGreaterThan(0)
    expect(screen.getAllByText('coingecko-public').length).toBeGreaterThan(0)
  })

  it('shows the status label, source and both timestamps for every quote', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    const usPanel = await screen.findByRole('article', { name: 'UNITED STATES market' })
    const aaplRow = within(usPanel).getByRole('row', { name: /AAPL/ })
    const msftRow = within(usPanel).getByRole('row', { name: /MSFT/ })
    expect(within(aaplRow).getByText('HISTORICAL')).toBeInTheDocument()
    expect(within(msftRow).getByText('UNAVAILABLE')).toBeInTheDocument()
    expect(within(aaplRow).getByText('yahoo-us-equities')).toBeInTheDocument()
    expect(within(aaplRow).getByText('2026-11-25T20:00:00Z')).toBeInTheDocument()
    expect(within(aaplRow).getByText(NOW)).toBeInTheDocument()
    expect(within(aaplRow).getByText('AGE 16h')).toBeInTheDocument()
    expect(within(aaplRow).getByText('2026-11-25T09:30:00-05:00')).toBeInTheDocument()
  })

  it('never renders a price for an unavailable quote', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    const usPanel = await screen.findByRole('article', { name: 'UNITED STATES market' })
    const msftRow = within(usPanel).getByRole('row', { name: /MSFT/ })
    // LAST and CHG both render an em dash for an unavailable row.
    expect(within(msftRow).getAllByText('—').length).toBe(2)
    expect(within(msftRow).queryByText(/USD/)).not.toBeInTheDocument()
    expect(within(msftRow).queryByText(/%/)).not.toBeInTheDocument()
    expect(within(usPanel).getByText(/1 instrument\(s\) reported UNAVAILABLE/)).toBeInTheDocument()
  })

  it('flags a stale quote without hiding it', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    const cryptoPanel = await screen.findByRole('article', { name: 'CRYPTOCURRENCY market' })
    expect(within(cryptoPanel).getByText('ALL OBSERVATIONS STALE')).toBeInTheDocument()
    expect(within(cryptoPanel).getByText('STALE 30m')).toBeInTheDocument()
    const btcRow = within(cryptoPanel).getByRole('row', { name: /BTCUSD/ })
    expect(within(btcRow).getByText('DELAYED')).toBeInTheDocument()
    expect(within(btcRow).getByText('95,000.50 USD')).toBeInTheDocument()
  })

  it('states that no attested source means live labels are unavailable', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByText(/NO ATTESTED SOURCE — LIVE\/DELAYED UNAVAILABLE/)).toBeInTheDocument()
    expect(screen.getByText(/3 USABLE \/ 5 ROWS/)).toBeInTheDocument()
    expect(screen.getByText('2 UNAVAILABLE')).toBeInTheDocument()
  })

  it('reports attested sources when the operator has attested one', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot({ attested_sources: ['yahoo-us-equities'] })),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByText('ATTESTED: yahoo-us-equities')).toBeInTheDocument()
  })

  it('requests a fresh fetch when the refresh control is used', async () => {
    const { user, calls } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')
    await screen.findByRole('article', { name: 'UNITED STATES market' })

    await user.click(screen.getByRole('button', { name: 'REFRESH BOARD' }))
    const urls = calls.filter(c => c.url.includes('/api/terminal/four-market')).map(c => c.url)
    expect(urls.length).toBe(2)
    expect(urls[1]).toContain('refresh=true')
  })

  it('surfaces a backend error instead of an empty board', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json({ detail: 'instrument master unavailable' }, 503),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByRole('alert')).toHaveTextContent('instrument master unavailable')
    expect(screen.queryByRole('article', { name: 'UNITED STATES market' })).not.toBeInTheDocument()
  })

  it('declares the execution boundary in the footer', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByText(/BROKER FALSE/)).toBeInTheDocument()
    expect(screen.getByText(/REAL MONEY FALSE/)).toBeInTheDocument()
    expect(screen.getByText(/RESEARCH AND DISPLAY ONLY/)).toBeInTheDocument()
  })

  it('exposes the status legend so labels cannot be misread', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    const legend = await screen.findByLabelText('Status label legend')
    for (const label of ['LIVE', 'DELAYED', 'HISTORICAL', 'SYNTHETIC', 'UNAVAILABLE']) {
      expect(within(legend).getByText(label)).toBeInTheDocument()
    }
  })

  it('opens the research tab when a symbol is selected', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot()),
    })
    await clickTab(user, 'FOUR MARKETS')

    const usPanel = await screen.findByRole('article', { name: 'UNITED STATES market' })
    await user.click(within(usPanel).getByRole('button', { name: 'AAPL' }))

    expect(await screen.findByRole('button', { name: /^RESEARCH$/ })).toHaveClass('active')
  })

  it('reports a market that is absent from the catalogue rather than inventing rows', async () => {
    const { user } = setupApp({
      'GET /api/terminal/four-market': () => json(snapshot({
        markets: [market({
          market_group: 'india', market_status: 'unavailable', headline: 'NOT IN CATALOGUE',
          requested: 0, usable_count: 0, unavailable_count: 0, quotes: [],
          note: 'No reference instrument for this market is registered in the instrument master.',
        })],
      })),
    })
    await clickTab(user, 'FOUR MARKETS')

    expect(await screen.findByText('NOT IN CATALOGUE')).toBeInTheDocument()
    expect(screen.getByText(/Coverage is reported as missing, not inferred|No reference instrument/)).toBeInTheDocument()
  })
})
