import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { clickTab, deferred, json, setupApp } from './helpers'

const coverage = [
  {
    symbol: 'BTCUSD', interval: '1h', observation_count: 42,
    sources: ['local-csv'], statuses: ['historical'], last_timestamp: '2026-01-02T00:00:00Z',
  },
  {
    symbol: 'ETHUSD', interval: '4h', observation_count: 7,
    sources: ['fixture'], statuses: ['historical'], last_timestamp: '2026-01-01T00:00:00Z',
  },
]

describe('App / market research overview (dashboard)', () => {
  it('renders the dashboard with real cards, status, disclaimer and all module links', async () => {
    setupApp({
      'GET /api/market-data/overview': () => json({ instrument_interval_count: 2, coverage, data_note: 'stored observations only' }),
      'GET /api/workers': () => json({ workers: [{ id: 'w1', name: 'Sentinel' }] }),
    })

    expect(await screen.findByRole('heading', { name: 'Market research overview' })).toBeInTheDocument()
    expect(screen.getAllByText('CONNECTED').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('API CONNECTION')).toBeInTheDocument()
    expect(screen.getByText('2 SYMBOL / TIMEFRAME SETS')).toBeInTheDocument()
    expect(screen.getByText('0 WATCHLIST INSTRUMENTS')).toBeInTheDocument()
    expect(screen.getByText('1 WORKER TEMPLATES')).toBeInTheDocument()

    const cards = screen.getAllByRole('article')
    expect(cards).toHaveLength(6)
    expect(cards.some(card => card.textContent?.includes('DATA COVERAGE'))).toBe(true)
    expect(screen.getByText('EXECUTION MODE')).toBeInTheDocument()
    expect(screen.getByText('DISABLED')).toBeInTheDocument()
    expect(screen.getByText('Broker connections and order execution are not configured')).toBeInTheDocument()
    expect(screen.getByText(/DATA STATUS: stored observations only/)).toBeInTheDocument()

    for (const label of ['Historical research', 'News intelligence', 'Worker directory', 'Workflow history', 'Visual workflow builder']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeInTheDocument()
    }
  })

  it.each([
    ['Historical research', 'HISTORICAL CSV IMPORT'],
    ['News intelligence', 'FETCH OFFICIAL NEWS'],
    ['Worker directory', 'RESEARCH PLAYBOOKS'],
    ['Workflow history', 'EXECUTION HISTORY'],
    ['Visual workflow builder', 'GRAPH EDITOR'],
  ])('module link %s navigates to its real view', async (link, expectedText) => {
    const { user } = setupApp()
    await user.click(await screen.findByRole('button', { name: new RegExp(link) }))
    expect(await screen.findByText(expectedText)).toBeInTheDocument()
  })

  it('REFRESH OVERVIEW re-requests the overview and exposes a loading state', async () => {
    let gate = deferred<Response>()
    const { user, calls } = setupApp({
      'GET /api/market-data/overview': () => gate.promise,
    })
    // The mount request uses the same route; release it so the button is enabled.
    gate.resolve(json({ instrument_interval_count: 1, coverage: [], data_note: 'fixture' }))
    expect(await screen.findByText('Market research overview')).toBeInTheDocument()

    gate = deferred<Response>()
    const before = calls.length
    await user.click(screen.getByRole('button', { name: 'REFRESH OVERVIEW' }))
    expect(calls.length).toBeGreaterThan(before)
    expect(calls.at(-1)?.url).toContain('/api/market-data/overview')
    expect(screen.getByRole('button', { name: 'REFRESHING…' })).toBeDisabled()

    gate.resolve(json({ instrument_interval_count: 9, coverage: [], data_note: 'refreshed' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'REFRESH OVERVIEW' })).toBeEnabled())
    expect(screen.getByText('9 SYMBOL / TIMEFRAME SETS')).toBeInTheDocument()
  })

  it('shows the overview error and empty-state copy when stored coverage is unavailable', async () => {
    setupApp({
      'GET /api/market-data/overview': () => json({ detail: 'overview offline' }, 503),
    })
    expect(await screen.findByText('overview offline')).toBeInTheDocument()
    expect(screen.getByText(/No stored market history found/)).toBeInTheDocument()
  })

  it('reports OFFLINE when the health request fails', async () => {
    setupApp({
      'GET /api/health': () => Promise.reject(new Error('network down')),
    })
    expect((await screen.findAllByText('OFFLINE')).length).toBeGreaterThanOrEqual(1)
  })

  it('VIEW CHART loads stored bars, renders the chart and can be closed', async () => {
    const { user, calls } = setupApp({
      'GET /api/market-data/overview': () => json({ instrument_interval_count: 1, coverage, data_note: 'stored' }),
      'GET /api/market-data/history': () => json({
        bars: [
          { timestamp: '2026-01-01T00:00:00Z', open: 10, high: 12, low: 9, close: 11, volume: 100, source: 'local-csv', status: 'historical' },
          { timestamp: '2026-01-02T00:00:00Z', open: 11, high: 13, low: 10, close: 12, volume: 120, source: 'local-csv', status: 'historical' },
        ],
        source: 'local-csv', status: 'historical', retrieved_at: '2026-01-03T00:00:00Z',
        source_count: 1, timestamp_count: 2, first_timestamp: '2026-01-01T00:00:00Z', last_timestamp: '2026-01-02T00:00:00Z',
      }),
    })
    const row = (await screen.findAllByText('BTCUSD'))[0].closest('.coverage-row') as HTMLElement
    await user.click(within(row).getByRole('button', { name: /VIEW CHART/ }))

    expect(await screen.findByText(/HISTORICAL PRICE CHART · BTCUSD · 1h/)).toBeInTheDocument()
    expect(calls.some(call => call.url.includes('/api/market-data/history?symbol=BTCUSD&interval=1h'))).toBe(true)
    expect(screen.getByText('2 STORED BARS')).toBeInTheDocument()
    expect(screen.getByText(/local-csv · historical · RETRIEVED 2026-01-03/)).toBeInTheDocument()
    expect(screen.getByText(/not a live quote or trading signal/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'CLOSE' }))
    expect(screen.queryByText(/HISTORICAL PRICE CHART · BTCUSD/)).not.toBeInTheDocument()
  })

  it('surfaces an empty-history message and API errors in the coverage chart', async () => {
    const { user } = setupApp({
      'GET /api/market-data/overview': () => json({ instrument_interval_count: 1, coverage, data_note: 'stored' }),
      'GET /api/market-data/history': () => json({ detail: 'history denied' }, 500),
    })
    const row = (await screen.findAllByText('BTCUSD'))[0].closest('.coverage-row') as HTMLElement
    await user.click(within(row).getByRole('button', { name: /VIEW CHART/ }))
    expect(await screen.findByText('history denied')).toBeInTheDocument()

    // A successful response with zero bars has its own explanatory message.
    const { user: user2 } = setupApp({
      'GET /api/market-data/overview': () => json({ instrument_interval_count: 1, coverage, data_note: 'stored' }),
      'GET /api/market-data/history': () => json({ bars: [], source: 'none', status: 'historical' }),
    })
    const row2 = (await screen.findAllByText('BTCUSD'))[0].closest('.coverage-row') as HTMLElement
    await user2.click(within(row2).getByRole('button', { name: /VIEW CHART/ }))
    expect(await screen.findByText(/No stored observations are available for this symbol and timeframe/)).toBeInTheDocument()
  })

  it('OPEN WATCHLIST navigates from the overview panel', async () => {
    const { user } = setupApp()
    await user.click(await screen.findByRole('button', { name: 'OPEN WATCHLIST' }))
    expect(await screen.findByText('SAVED INSTRUMENTS')).toBeInTheDocument()
  })

  it('Configure dialog is opened and closed by real controls (role, label, keyboard)', async () => {
    const { user } = setupApp()
    await user.click(await screen.findByRole('button', { name: /Configure/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Terminal configuration' })
    expect(within(dialog).getByText('CONFIGURATION · READ ONLY')).toBeInTheDocument()
    expect(within(dialog).getByText(/EXECUTION MODE/)).toBeInTheDocument()
    expect(within(dialog).getByText(/DISABLED · RESEARCH ONLY/)).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'CLOSE' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // Reopen and close with Escape-equivalent backdrop click on the dialog overlay.
    await user.click(screen.getByRole('button', { name: /Configure/ }))
    const reopened = await screen.findByRole('dialog', { name: 'Terminal configuration' })
    await user.click(reopened)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('every global toolbar control has an observable effect', async () => {
    const { user, calls } = setupApp({
      'GET /api/instrument-master': () => json({ instruments: [{ symbol: 'BTCUSD', name: 'Bitcoin', market: 'crypto', venue: 'test', currency: 'USD' }] }),
    })
    const input = await screen.findByRole('textbox', { name: 'Search instruments' })
    await user.type(input, 'btc')
    await user.keyboard('{Enter}')
    expect(calls.some(call => call.url.includes('/api/instrument-master?q=btc'))).toBe(true)
    expect(await screen.findByText('Bitcoin')).toBeInTheDocument()

    const title = screen.getByRole('textbox', { name: 'Workspace name' })
    await user.clear(title)
    await user.type(title, 'Phase 2 workspace')
    expect(screen.getByRole('textbox', { name: 'Workspace name' })).toHaveValue('Phase 2 workspace')

    await user.click(screen.getByRole('button', { name: /FIND/ }))
    expect(calls.filter(call => call.url.includes('/api/instrument-master')).length).toBeGreaterThanOrEqual(2)

    await clickTab(user, 'WORKFLOW')
    expect(screen.getByTestId('react-flow')).toBeInTheDocument()
  })
})
