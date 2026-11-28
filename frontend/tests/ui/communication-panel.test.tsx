import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const board = () => ({
  generated_at: '2026-11-26T12:00:00Z', mode: 'four_market_research_terminal',
  market_groups: [], markets: [],
  totals: { markets: 0, quotes: 0, usable: 0, unavailable: 0, stale: 0 },
  legend: { labels: [], stale_rule: '' }, providers: { note: '' }, attested_sources: [],
  execution: { paper_trading: false, broker_execution: false, real_money: false },
})

const status = (overrides: Record<string, unknown> = {}) => ({
  configured: false, enabled: false, pending_count: 0, sent_count: 0,
  last_successful_sync: null,
  streams: { 'market-data': ['US-stocks'], 'ci-testing': ['GitHub-Actions'] },
  credentials_exposed: false, inbound_commands_enabled: false,
  broker_execution: false, real_money: false,
  ...overrides,
})

const ROUTES = {
  'GET /api/terminal/four-market': () => json(board()),
  'GET /api/terminal/bars/intervals': () => json({ intervals: [] }),
  'GET /api/intelligence/board': () => json({ venues: [] }),
  'GET /api/communication/status': () => json(status()),
}

describe('Optional communication panel', () => {
  it('shows unconfigured but non-blocking status', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Optional communication status' })

    expect(await within(panel).findByText('NOT CONFIGURED')).toBeInTheDocument()
    expect(within(panel).getByText('CREDENTIALS EXPOSED FALSE')).toBeInTheDocument()
    expect(within(panel).getByText('BROKER EXECUTION FALSE')).toBeInTheDocument()
    expect(within(panel).getByText(/existing agents, research engine and terminal remain authoritative/)).toBeInTheDocument()
  })

  it('shows connected status and last sync when configured', async () => {
    const { user } = setupApp({
      ...ROUTES,
      'GET /api/communication/status': () => json(status({
        configured: true, enabled: true, sent_count: 3,
        last_successful_sync: '2026-11-26T12:00:00Z',
      })),
    })
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Optional communication status' })

    expect(await within(panel).findByText('CONNECTED')).toBeInTheDocument()
    expect(within(panel).getByText(/2026-11-26T12:00:00Z/)).toBeInTheDocument()
  })

  it('states that inbound messages cannot trigger actions', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Optional communication status' })

    expect(await within(panel).findByText(/No chat commands are executed/)).toBeInTheDocument()
    expect(within(panel).getByText(/outages cannot stop MARKET-MIND-AI/)).toBeInTheDocument()
  })

  it('surfaces a status failure without disabling the terminal', async () => {
    const { user } = setupApp({
      ...ROUTES,
      'GET /api/communication/status': () => json({ detail: 'status unavailable' }, 503),
    })
    await clickTab(user, 'FOUR MARKETS')
    const panel = await screen.findByRole('region', { name: 'Optional communication status' })

    expect(await within(panel).findByRole('alert')).toHaveTextContent('status unavailable')
    expect(screen.queryByText('United States · India · Forex · Crypto')).toBeInTheDocument()
  })
})
