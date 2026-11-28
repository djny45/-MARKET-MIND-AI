import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const board = () => ({
  generated_at: '2026-11-26T12:00:00Z', mode: 'four_market_research_terminal',
  market_groups: ['us', 'india', 'forex', 'crypto'], markets: [],
  totals: { markets: 0, quotes: 0, usable: 0, unavailable: 0, stale: 0 },
  legend: { labels: [], stale_rule: '' }, providers: { note: '' },
  attested_sources: [],
  execution: { paper_trading: false, broker_execution: false, real_money: false },
})

const intel = () => ({
  generated_at: '2026-11-26T12:00:00Z',
  venues: [
    { venue: 'okx', status: 'historical', status_label: 'HISTORICAL', last: 60854.5,
      source: 'okx-public', age_seconds: 2, stale: false },
    { venue: 'coinbase', status: 'historical', status_label: 'HISTORICAL', last: 60780,
      source: 'coinbase-public', age_seconds: 3, stale: false },
  ],
  funding: { funding_rate: 0.0001, source: 'okx-public' },
  depth: { bid_depth_usd: 223194, source: 'okx-public' },
  sentiment: { value: 11, classification: 'Extreme Fear', source: 'alternative-sentiment' },
  gold: { symbol: 'PAXG', status_label: 'HISTORICAL', source: 'coingecko-gold-token' },
  flow: {
    summary: { flow_direction: 'buy_dominant', buy_notional: 700 },
    dots: { count: 1, dots: [{ time: '2026-11-26T12:00:00Z', side: 'buy', size: 1, notional: 700, colour: '#62b58e' }] },
  },
  brokers: { live_broker_data_available: false, brokers: [] },
  execution: { broker_execution: false, real_money: false },
  licensing: { live_claims_require_attestation: true, tredye_endpoints_used: false, adapters: 8 },
})

const ROUTES = {
  'GET /api/terminal/four-market': () => json(board()),
  'GET /api/terminal/bars/intervals': () => json({ intervals: [] }),
  'GET /api/intelligence/board': () => json(intel()),
}

describe('Exchange intelligence panel', () => {
  it('shows verified public venue data with source and status', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Exchange intelligence panel' })

    expect(within(panel).getByText('OKX')).toBeInTheDocument()
    expect(within(panel).getByText('COINBASE')).toBeInTheDocument()
    expect(within(panel).getAllByText('HISTORICAL').length).toBeGreaterThan(0)
    expect(within(panel).getByText('SOURCE okx-public')).toBeInTheDocument()
    expect(within(panel).getByText(/60,854.5/)).toBeInTheDocument()
  })

  it('states the research/educational and regulatory boundary', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Exchange intelligence panel' })

    expect(await within(panel).findByText(/not a broker or investment adviser/)).toBeInTheDocument()
    expect(within(panel).getByText(/No SEBI registration or regulatory approval is claimed/)).toBeInTheDocument()
    expect(within(panel).getByText(/BROKER EXECUTION FALSE/)).toBeInTheDocument()
    expect(within(panel).getByText(/REAL MONEY FALSE/)).toBeInTheDocument()
  })

  it('states that Tredye endpoints are not used and broker credentials are isolated', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Exchange intelligence panel' })

    expect(await within(panel).findByText(/TREDYE ENDPOINTS USED false/)).toBeInTheDocument()
    expect(within(panel).getByText((_content, element) =>
      !!element && element.tagName === 'P' &&
      /no broker credentials are stored or sent to this backend/i.test(element.textContent || '')
    )).toBeInTheDocument()
  })

  it('surfaces an intelligence failure instead of empty data', async () => {
    const { user } = setupApp({
      ...ROUTES,
      'GET /api/intelligence/board': () => json({ detail: 'provider unavailable' }, 502),
    })
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Exchange intelligence panel' })

    expect(await within(panel).findByRole('alert')).toHaveTextContent('provider unavailable')
    expect(within(panel).queryByText('OKX')).not.toBeInTheDocument()
  })
})
