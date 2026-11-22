import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { bodyOf, clickTab, json, setupApp, type FetchCall } from './helpers'
import { __flowTest } from './mocks/xyflow'

const skills = [
  { id: 'trader-momentum-research', description: 'Historical momentum context', available: true },
  { id: 'trader-data-quality', description: 'Validation playbook', available: true },
  { id: 'trader-unavailable-playbook', description: 'Hidden', available: false },
]
const workers = [
  { id: 'w1', name: 'Data Quality Sentinel', department: 'validation', specialty: 'Data validation', skill_refs: ['trader-data-quality'] },
  { id: 'w2', name: 'Trend Analyst', department: 'technical_research', specialty: 'Trend research', skill_refs: [] },
]

describe('App / worker and skill interface + workflow graph', () => {
  it('lists only available skills and all workers, and filters workers by search', async () => {
    const { user } = setupApp({
      'GET /api/skills': () => json({ skills }),
      'GET /api/workers': () => json({ workers }),
    })
    await clickTab(user, 'AGENT DIRECTORY')

    expect(await screen.findByText('momentum research')).toBeInTheDocument()
    expect(screen.getByText('data quality')).toBeInTheDocument()
    expect(screen.queryByText('unavailable playbook')).not.toBeInTheDocument()
    expect(screen.getByText('0 SELECTED')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Data Quality Sentinel/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Trend Analyst/ })).toBeInTheDocument()

    const search = screen.getByPlaceholderText('Search 550 worker profiles…')
    await user.type(search, 'trend')
    expect(screen.getByRole('button', { name: /Trend Analyst/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Data Quality Sentinel/ })).not.toBeInTheDocument()
    await user.clear(search)
    expect(await screen.findByRole('button', { name: /Data Quality Sentinel/ })).toBeInTheDocument()
  })

  it('toggling skill checkboxes updates selection and is included in the run payload', async () => {
    const { user, calls } = setupApp({
      'GET /api/skills': () => json({ skills }),
      'GET /api/workers': () => json({ workers }),
    })
    await clickTab(user, 'AGENT DIRECTORY')
    const checkbox = await screen.findByRole('checkbox', { name: /momentum research/ })
    await user.click(checkbox)
    expect(checkbox).toBeChecked()
    expect(screen.getByText('1 SELECTED')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Data Quality Sentinel/ }))
    await clickTab(user, 'WORKFLOW')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '7')

    await user.click(screen.getByRole('button', { name: /RUN WORKFLOW/ }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/workflows/execute') && call.method === 'POST')).toBe(true))
    const post = calls.find(call => call.url.endsWith('/api/workflows/execute')) as FetchCall
    const payload = bodyOf(post.init)
    expect(payload.skill_ids).toEqual(expect.arrayContaining(['trader-momentum-research', 'trader-data-quality']))
    expect(payload.nodes).toHaveLength(7)
    expect(payload.edges.length).toBeGreaterThanOrEqual(6)
    expect(payload.inputs.data).toEqual([100, 101, 99, 103, 105, 104, 108, 107, 110, 112, 111, 115])
  })

  it('all ten palette items add a node; connect handler adds an edge', async () => {
    const { user } = setupApp()
    await clickTab(user, 'WORKFLOW')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '6')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-edge-count', '6')

    const palette = document.querySelectorAll('.palette-item')
    expect(palette).toHaveLength(10)
    for (let i = 0; i < palette.length; i++) {
      await user.click(palette[i])
    }
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '16')

    const before = Number(screen.getByTestId('react-flow').getAttribute('data-edge-count'))
    __flowTest.connect({ source: 'feed', target: 'report' })
    await waitFor(() => expect(Number(screen.getByTestId('react-flow').getAttribute('data-edge-count'))).toBe(before + 1))
  })

  it('RUN WORKFLOW shows busy, success and error outcomes', async () => {
    let gate = Promise.resolve(json({ status: 'completed', run_id: 'r1' }))
    const { user } = setupApp({
      'POST /api/workflows/execute': () => gate,
    })
    await clickTab(user, 'WORKFLOW')
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(screen.getByRole('button', { name: /RUN WORKFLOW/ }))
    expect(screen.getByRole('button', { name: 'RUNNING…' })).toBeDisabled()

    resolve(json({ status: 'completed', aggregation: { completed_count: 2, task_count: 2, failed_count: 0, skipped_count: 0, result_count: 2 }, tasks: [], performance: { total_execution_ns: 1000000 } }))
    expect(await screen.findByText('EXECUTION INSPECTOR')).toBeInTheDocument()
    expect(screen.getByText('ORCHESTRATION SUMMARY')).toBeInTheDocument()
    expect(screen.getByText(/2\/2 completed/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close execution inspector' }))
    expect(screen.queryByText('EXECUTION INSPECTOR')).not.toBeInTheDocument()
  })

  it('execution API failure renders an error result rather than a success', async () => {
    const { user } = setupApp({
      'POST /api/workflows/execute': () => json({ detail: 'engine refused' }, 500),
    })
    await clickTab(user, 'WORKFLOW')
    await user.click(screen.getByRole('button', { name: /RUN WORKFLOW/ }))
    expect(await screen.findByText('EXECUTION INSPECTOR')).toBeInTheDocument()
    expect(screen.getByText(/engine refused/)).toBeInTheDocument()
  })

  it('LOAD SYNTHETIC SAMPLE replaces the input series with clearly labelled fixture data', async () => {
    const { user, calls } = setupApp({
      'GET /api/market-data/sample': url => {
        expect(url.searchParams.get('symbol')).toBe('BTCUSD')
        expect(url.searchParams.get('limit')).toBe('5')
        return json({ symbol: 'BTCUSD', interval: '1d', source: 'synthetic-fixture', status: 'fixture', retrieved_at: '2026-01-01T00:00:00Z', warnings: ['not market prices'], bars: [{ close: 10 }, { close: 11 }, { close: 12 }, { close: 13 }, { close: 14 }] })
      },
    })
    await clickTab(user, 'WORKFLOW')
    await user.click(screen.getByRole('button', { name: 'LOAD SYNTHETIC SAMPLE' }))
    await waitFor(() => expect(calls.some(call => call.url.includes('/api/market-data/sample'))).toBe(true))
    expect(screen.getByRole('textbox', { name: 'Comma-separated market data values' })).toHaveValue('10,11,12,13,14')
    expect(screen.getByText(/SYNTHETIC FIXTURE · NOT MARKET PRICES/)).toBeInTheDocument()
    expect(await screen.findByText('EXECUTION INSPECTOR')).toBeInTheDocument()

    // Editing the input immediately re-labels it as manual demo data.
    await user.type(screen.getByRole('textbox', { name: 'Comma-separated market data values' }), ',15')
    expect(screen.getByText(/MANUAL DEMO INPUT/)).toBeInTheDocument()
  })

  it('the graph toolbar exposes a Classic Terminal link and the research-only banner', () => {
    setupApp()
    expect(screen.getByRole('link', { name: 'CLASSIC TERMINAL' })).toHaveAttribute('target', '_blank')
    expect(screen.getByText('NO EXECUTION LAYER')).toBeInTheDocument()
    expect(within(screen.getByRole('contentinfo')).getByText(/HISTORICAL RESEARCH ONLY/)).toBeInTheDocument()
  })
})
