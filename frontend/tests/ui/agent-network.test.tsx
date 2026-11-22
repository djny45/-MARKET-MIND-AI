import { act, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { setupAgentNetwork } from './helpers'

const agents = [
  { id: 'agent-1', name: 'Trend Analyst', department: 'technical_research', specialty: 'Momentum', status: 'REGISTERED' },
  { id: 'agent-2', name: 'Data Sentinel', department: 'validation', specialty: 'Quality', status: 'REGISTERED' },
  { id: 'agent-3', name: 'Liquidity Analyst', department: 'technical_research', specialty: 'Volume', status: 'REGISTERED' },
]

describe('AgentNetwork component', () => {
  it('renders real registered profiles, the shared core and the research-only legend', async () => {
    setupAgentNetwork(agents)
    expect(await screen.findByRole('heading', { name: /550\+ Analytical Agent Network/ })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '4') // core + 3 agents
    expect(screen.getByTestId('flow-node-intelligence-core')).toHaveTextContent('MARKET-MIND AI')
    expect(screen.getByTestId('flow-node-agent-1')).toHaveTextContent('Trend Analyst')
    expect(screen.getByText(/no paper trading/i)).toBeInTheDocument()
    expect(screen.getByText(/not proof that every agent is currently running/i)).toBeInTheDocument()
  })

  it('loads persisted task activity and reports an API failure without hiding profiles', async () => {
    const { unmount } = setupAgentNetwork(agents, {
      'GET /api/agent-network/activity': () => new Response(JSON.stringify({ task_count: 12, status_counts: { running: 2, queued: 3 }, latest_by_agent: { 'agent-1': { status: 'running', task_id: 't1', updated_at: 'now' } }, note: 'fixture' }), { status: 200 }),
    })
    expect(await screen.findByText(/TASK ACTIVITY · 12 persisted tasks/)).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText(/RUNNING TASKS/)).toBeInTheDocument()
    expect(screen.getByTestId('flow-node-agent-1')).toHaveTextContent('RUNNING')
    unmount()

    setupAgentNetwork(agents, {
      'GET /api/agent-network/activity': () => Promise.reject(new Error('down')),
    })
    expect(await screen.findByText('API activity unavailable — showing registered profiles only')).toBeInTheDocument()
    expect(screen.getByTestId('flow-node-agent-2')).toBeInTheDocument()
  })

  it('search, department filter and RESET FILTERS all update the visible profile set', async () => {
    const { user } = setupAgentNetwork(agents)
    const search = await screen.findByRole('textbox', { name: 'Search agent network' })
    await user.type(search, 'liquidity')
    expect(screen.getByText('1 / 3 profiles visible')).toBeInTheDocument()
    expect(screen.queryByTestId('flow-node-agent-1')).not.toBeInTheDocument()
    expect(screen.getByTestId('flow-node-agent-3')).toBeInTheDocument()

    await user.clear(search)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by department' }), 'validation')
    expect(screen.getByText('1 / 3 profiles visible')).toBeInTheDocument()
    expect(screen.getByTestId('flow-node-agent-2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'RESET FILTERS' }))
    expect(screen.getByText('3 / 3 profiles visible')).toBeInTheDocument()
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '4')
    expect((search as HTMLInputElement).value).toBe('')
  })

  it('clicking a node opens the inspector and CLOSE dismisses it', async () => {
    const { user } = setupAgentNetwork(agents)
    await user.click(await screen.findByTestId('flow-node-agent-2'))
    const inspector = await screen.findByRole('button', { name: 'CLOSE' })
    expect(inspector.closest('.agent-network-inspector')).toHaveTextContent('Data Sentinel')
    expect(inspector.closest('.agent-network-inspector')).toHaveTextContent('validation')
    await user.click(inspector)
    expect(document.querySelector('.agent-network-inspector')).not.toBeInTheDocument()
  })

  it('polls the activity endpoint every 20 seconds', async () => {
    vi.useFakeTimers()
    try {
      let count = 0
      const { calls } = setupAgentNetwork(agents, {
        'GET /api/agent-network/activity': () => { count++; return new Response(JSON.stringify({ task_count: count, status_counts: {}, latest_by_agent: {}, note: 'fixture' }), { status: 200 }) },
      })
      await act(async () => { await Promise.resolve() })
      expect(count).toBe(1)
      await act(async () => { vi.advanceTimersByTime(20000) })
      expect(count).toBe(2)
      expect(calls.filter(call => call.url.includes('/api/agent-network/activity'))).toHaveLength(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('filter controls are labelled for keyboard/screen-reader users', async () => {
    setupAgentNetwork(agents)
    expect(await screen.findByRole('textbox', { name: 'Search agent network' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Filter by department' })).toBeInTheDocument()
    expect(within(screen.getByRole('button', { name: 'RESET FILTERS' })).getByText('RESET FILTERS')).toBeInTheDocument()
  })
})
