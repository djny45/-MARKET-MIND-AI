import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const board = () => ({
  generated_at: '2026-11-26T12:00:00Z', mode: 'four_market_research_terminal',
  market_groups: ['us', 'india', 'forex', 'crypto'], markets: [],
  totals: { markets: 0, quotes: 0, usable: 0, unavailable: 0, stale: 0 },
  legend: { labels: [], stale_rule: '' }, providers: { note: '' }, attested_sources: [],
  execution: { paper_trading: false, broker_execution: false, real_money: false },
})

const ROUTES = {
  'GET /api/terminal/four-market': () => json(board()),
  'GET /api/terminal/bars/intervals': () => json({ intervals: [] }),
  'GET /api/intelligence/board': () => json({ venues: [] }),
  'GET /api/intelligence/order-flow': () => json({ summary: { flow_direction: 'unavailable' } }),
  'GET /api/intelligence/order-book/replay': () => json({
    replay: { valid: false, status: 'unavailable_sequence_gap_or_missing_snapshot' },
  }),
  'GET /api/intelligence/okx/derivatives': () => json({ source: 'okx-public', funding_rate: 0.0001 }),
  'GET /api/intelligence/deribit/options': () => json({ options: { count: 2 } }),
  'GET /api/intelligence/liquidations': () => json({ liquidation_events: 0 }),
  'GET /api/paper/backtest/run': () => json({ mode: 'historical_backtest', broker_execution: false }),
}

describe('Market structure research views', () => {
  it('offers all seven research views with no second terminal', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const views = await screen.findByRole('region', { name: 'Market structure research views' })

    for (const label of ['OVERVIEW', 'MONEY FLOW', 'ORDER BOOK', 'OI / FUNDING / BASIS',
                         'OPTIONS', 'LIQUIDATIONS', 'BACKTESTING']) {
      expect(within(views).getByRole('tab', { name: label })).toBeInTheDocument()
    }
  })

  it('loads order-book replay and shows sequence-gap status', async () => {
    const { user, calls } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const views = await screen.findByRole('region', { name: 'Market structure research views' })

    await user.click(within(views).getByRole('tab', { name: 'ORDER BOOK' }))
    expect(await within(views).findByTestId('research-view-payload')).toHaveTextContent(
      'unavailable_sequence_gap_or_missing_snapshot'
    )
    expect(calls.some(c => c.url.includes('/api/intelligence/order-book/replay'))).toBe(true)
  })

  it('shows backtesting as historical research with no execution', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const views = await screen.findByRole('region', { name: 'Market structure research views' })

    await user.click(within(views).getByRole('tab', { name: 'BACKTESTING' }))
    expect(await within(views).findByTestId('research-view-payload')).toHaveTextContent(
      'historical_backtest'
    )
    expect(within(views).getByText(/No broker execution or autonomous trading/)).toBeInTheDocument()
  })

  it('surfaces an unavailable view instead of inventing data', async () => {
    const { user } = setupApp({
      ...ROUTES,
      'GET /api/intelligence/deribit/options': () => json({ detail: 'provider unavailable' }, 502),
    })
    await clickTab(user, 'FOUR MARKETS')
    const views = await screen.findByRole('region', { name: 'Market structure research views' })

    await user.click(within(views).getByRole('tab', { name: 'OPTIONS' }))
    expect(await within(views).findByRole('alert')).toHaveTextContent('provider unavailable')
    expect(within(views).queryByTestId('research-view-payload')).not.toBeInTheDocument()
  })
})
