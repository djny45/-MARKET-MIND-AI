import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import { ObservationScreener, CoverageHeatmap, type CoverageRow } from '../../src/CoverageTools'
import { setupUi } from './helpers'

const coverage: CoverageRow[] = [
  { symbol: 'AAPL', interval: '1d', observation_count: 120, sources: ['historical-csv'], statuses: ['historical'], last_timestamp: '2026-01-02T00:00:00Z' },
  { symbol: 'AAPL', interval: '1h', observation_count: 4, sources: ['historical-csv'], statuses: ['historical'], last_timestamp: '2026-01-01T00:00:00Z' },
  { symbol: 'MSFT', interval: '1d', observation_count: 35, sources: ['historical-csv'], statuses: ['historical'], last_timestamp: '2026-01-02T00:00:00Z' },
]

const base = { coverage, loading: false, error: null, onLoad: vi.fn() }

describe('ObservationScreener', () => {
  it('filters by symbol, timeframe and minimum observation count', async () => {
    const { user } = setupUi(<ObservationScreener {...base} />)
    expect(await screen.findByText(/3 MATCHES/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Filter by symbol'), 'aapl')
    expect(screen.getByText(/2 MATCHES/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Filter by timeframe'), '1d')
    expect(screen.getByText(/1 MATCHES/)).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Minimum observation count'))
    await user.type(screen.getByLabelText('Minimum observation count'), '200')
    expect(screen.getByText(/0 MATCHES/)).toBeInTheDocument()
    expect(screen.getByText(/No stored observations match these filters/)).toBeInTheDocument()
  })

  it('renders loading, error and empty states without inventing live data', async () => {
    setupUi(<ObservationScreener {...base} loading error={null} />)
    expect(screen.getByRole('status')).toHaveTextContent('LOADING STORED OBSERVATIONS')
    expect(screen.getByText(/NOT LIVE MARKET DATA/)).toBeInTheDocument()
  })

  it('surfaces a backend error', async () => {
    setupUi(<ObservationScreener {...base} error="coverage unavailable" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('coverage unavailable')
  })

  it('calls the load action', async () => {
    const onLoad = vi.fn()
    const { user } = setupUi(<ObservationScreener {...base} onLoad={onLoad} />)
    await user.click(screen.getByRole('button', { name: /LOAD STORED OBSERVATIONS/ }))
    expect(onLoad).toHaveBeenCalledOnce()
  })
})

describe('CoverageHeatmap', () => {
  it('renders symbol x timeframe coverage intensity with a legend', async () => {
    setupUi(<CoverageHeatmap {...base} />)
    const table = await screen.findByRole('table')
    expect(within(table).getByText('AAPL')).toBeInTheDocument()
    expect(within(table).getByText('MSFT')).toBeInTheDocument()
    expect(within(table).getByText('120')).toBeInTheDocument()
    expect(screen.getByText('COVERAGE INTENSITY (OBSERVATIONS STORED)')).toBeInTheDocument()
    expect(screen.getByText('100+')).toBeInTheDocument()
  })

  it('labels cells as stored observation coverage, never price or liquidity', async () => {
    setupUi(<CoverageHeatmap {...base} />)
    const cells = await screen.findAllByLabelText(/stored observations, .* coverage/)
    expect(cells.length).toBeGreaterThan(0)
    expect(cells[0]).toHaveAttribute('title', expect.stringContaining('stored observations'))
    expect(screen.getByText(/NOT LIVE MARKET DATA/)).toBeInTheDocument()
  })

  it('shows an explicit empty state when no observations are stored', async () => {
    setupUi(<CoverageHeatmap {...base} coverage={[]} />)
    expect(await screen.findByText(/No stored coverage yet/)).toBeInTheDocument()
  })
})
