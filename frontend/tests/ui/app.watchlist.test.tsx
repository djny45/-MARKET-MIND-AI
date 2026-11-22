import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { bodyOf, clickTab, json, setupApp, type FetchCall } from './helpers'

const instruments = [
  { symbol: 'BTCUSD', name: 'Bitcoin', market: 'crypto', venue: 'fixture', currency: 'USD' },
]

function watchlistRoutes(saved: string[]) {
  return {
    'GET /api/watchlist': () => json({ symbols: saved.map(symbol => ({ symbol, added_at: '2026-01-01T00:00:00Z' })) }),
    'GET /api/instrument-master': () => json({ instruments }),
  }
}

describe('App / watchlist and instrument search', () => {
  it('renders the empty state and REFRESH WATCHLIST / LOAD MARKET DATA OVERVIEW re-request data', async () => {
    const { user, calls } = setupApp(watchlistRoutes([]))
    await clickTab(user, 'WATCHLIST')

    expect(await screen.findByText(/No saved instruments yet/)).toBeInTheDocument()
    const before = calls.length
    await user.click(screen.getByRole('button', { name: 'REFRESH WATCHLIST' }))
    expect(calls.length).toBeGreaterThan(before)
    expect(calls.at(-1)?.url).toContain('/api/watchlist')

    await user.click(screen.getByRole('button', { name: 'LOAD MARKET DATA OVERVIEW' }))
    await waitFor(() => expect(calls.some(call => call.url.includes('/api/market-data/overview'))).toBe(true))
  })

  it('loads and displays locally stored coverage and exposes an overview error', async () => {
    const { user } = setupApp({
      ...watchlistRoutes([]),
      'GET /api/market-data/overview': () => json({
        instrument_interval_count: 1,
        coverage: [{ symbol: 'ETHUSD', interval: '4h', observation_count: 3, sources: ['local-csv'], statuses: ['historical'], last_timestamp: '2026-01-02T00:00:00Z' }],
        data_note: 'stored data only',
      }),
    })
    await clickTab(user, 'WATCHLIST')
    await user.click(screen.getByRole('button', { name: 'LOAD MARKET DATA OVERVIEW' }))
    expect(await screen.findByText('1 SYMBOL / TIMEFRAME SETS')).toBeInTheDocument()
    expect(screen.getByText(/3 observations/)).toBeInTheDocument()
    expect(screen.getByText(/stored data only/)).toBeInTheDocument()
  })

  it('surfaces an overview API error in the watchlist sidebar', async () => {
    const { user } = setupApp({
      ...watchlistRoutes([]),
      'GET /api/market-data/overview': () => json({ detail: 'coverage unavailable' }, 500),
    })
    await clickTab(user, 'WATCHLIST')
    expect((await screen.findAllByText('coverage unavailable')).length).toBeGreaterThanOrEqual(1)
  })

  it('ADD TO WATCHLIST posts the chosen symbol and shows the success/already-saved messages', async () => {
    const saved: string[] = []
    let already = false
    const { user, calls } = setupApp({
      ...watchlistRoutes(saved),
      'POST /api/watchlist': (_url, init) => {
        const { symbol } = bodyOf(init)
        if (already) return json({ symbol, already_present: true })
        saved.push(symbol)
        return json({ symbol, already_present: false })
      },
    })
    await clickTab(user, 'WATCHLIST')
    const search = await screen.findByRole('textbox', { name: 'Search instruments' })
    await user.type(search, 'BTC')
    await user.keyboard('{Enter}')
    const result = await screen.findByText('Bitcoin')
    await user.click(within(result.closest('div') as HTMLElement).getByRole('button', { name: 'ADD TO WATCHLIST' }))

    await waitFor(() => expect(calls.some(call => call.method === 'POST' && call.url.endsWith('/api/watchlist'))).toBe(true))
    const post = calls.find(call => call.method === 'POST' && call.url.endsWith('/api/watchlist')) as FetchCall
    expect(bodyOf(post.init).symbol).toBe('BTCUSD')
    expect(await screen.findByText('BTCUSD ADDED')).toBeInTheDocument()
    expect((await screen.findAllByText('BTCUSD')).some(el => el.closest('.aligned-row'))).toBe(true)

    already = true
    await user.click(within((await screen.findByText('Bitcoin')).closest('div') as HTMLElement).getByRole('button', { name: 'ADD TO WATCHLIST' }))
    expect(await screen.findByText('BTCUSD ALREADY SAVED')).toBeInTheDocument()
  })

  it('surfaces watchlist POST errors instead of claiming success', async () => {
    const { user } = setupApp({
      ...watchlistRoutes([]),
      'POST /api/watchlist': () => json({ detail: 'watchlist write denied' }, 403),
    })
    await clickTab(user, 'WATCHLIST')
    await user.type(await screen.findByRole('textbox', { name: 'Search instruments' }), 'BTC')
    await user.click(screen.getByRole('button', { name: /FIND/ }))
    await user.click(within((await screen.findByText('Bitcoin')).closest('div') as HTMLElement).getByRole('button', { name: 'ADD TO WATCHLIST' }))
    expect(await screen.findByText('watchlist write denied')).toBeInTheDocument()
  })

  it('REMOVE issues a DELETE and refreshes the list', async () => {
    const saved = ['BTCUSD']
    const { user, calls } = setupApp(watchlistRoutes(saved))
    await clickTab(user, 'WATCHLIST')
    const row = (await screen.findAllByText('BTCUSD'))[0].closest('.aligned-row') as HTMLElement
    await user.click(within(row).getByRole('button', { name: 'REMOVE' }))
    await waitFor(() => expect(calls.some(call => call.method === 'DELETE' && call.url.includes('/api/watchlist/BTCUSD'))).toBe(true))
    expect(await screen.findByText('BTCUSD REMOVED')).toBeInTheDocument()
  })

  it('RESEARCH in a watchlist row navigates with the chosen symbol', async () => {
    const { user } = setupApp(watchlistRoutes(['BTCUSD']))
    await clickTab(user, 'WATCHLIST')
    const row = (await screen.findAllByText('BTCUSD'))[0].closest('.aligned-row') as HTMLElement
    await user.click(within(row).getByRole('button', { name: 'RESEARCH' }))
    expect(await screen.findByText('HISTORICAL CSV IMPORT')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Research symbol' })).toHaveValue('BTCUSD')
  })

  it('LOAD MARKET DATA OVERVIEW shows its busy label while the request is pending', async () => {
    let gate = Promise.resolve(json({ instrument_interval_count: 0, coverage: [], data_note: 'fixture' }))
    const { user } = setupApp({
      ...watchlistRoutes([]),
      'GET /api/market-data/overview': () => gate,
    })
    await clickTab(user, 'WATCHLIST')
    const button = await screen.findByRole('button', { name: 'LOAD MARKET DATA OVERVIEW' })
    let resolveSecond!: (value: Response) => void
    gate = new Promise<Response>(resolve => { resolveSecond = resolve })
    await user.click(button)
    expect(screen.getByRole('button', { name: 'LOADING COVERAGE…' })).toBeDisabled()
    resolveSecond(json({ instrument_interval_count: 0, coverage: [], data_note: 'fixture' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'LOAD MARKET DATA OVERVIEW' })).toBeEnabled())
  })
})
