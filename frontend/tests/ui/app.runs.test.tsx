import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const runs = [
  { id: 'run-a', status: 'completed', created_at: '2026-01-01T00:00:00Z' },
  { id: 'run-b', status: 'failed_checkpoint', created_at: '2026-01-02T00:00:00Z', parent_run_id: 'run-a' },
]

describe('App / execution history and checkpoint replay', () => {
  it('RUNS tab loads history and lists each real run', async () => {
    const { calls, user } = setupApp({ 'GET /api/workflows/runs': () => json({ runs }) })
    await clickTab(user, 'RUNS')
    expect(await screen.findByText('EXECUTION HISTORY')).toBeInTheDocument()
    expect(calls.some(call => call.url.includes('/api/workflows/runs?limit=50'))).toBe(true)
    expect(screen.getByText(/2 RUNS/)).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('FAILED CHECKPOINT')).toBeInTheDocument()
    expect(screen.getByText('Replay of run-a')).toBeInTheDocument()
  })

  it('REFRESH HISTORY re-requests runs and reports an API error', async () => {
    const { calls, user } = setupApp({
      'GET /api/workflows/runs': () => json({ detail: 'history denied' }, 500),
    })
    await clickTab(user, 'RUNS')
    expect(await screen.findAllByText('history denied')).toBeTruthy()
    const before = calls.length
    await user.click(screen.getByRole('button', { name: 'REFRESH HISTORY' }))
    expect(calls.length).toBeGreaterThan(before)
  })

  it('inspecting a run fetches its record and CLOSE DETAILS clears it', async () => {
    const { calls, user } = setupApp({
      'GET /api/workflows/runs': () => json({ runs }),
      'GET /api/workflows/runs/:id': url => json({
        id: url.pathname.split('/').at(-1), status: 'completed', created_at: '2026-01-02T00:00:00Z',
        result: { aggregation: { completed_count: 3, failed_count: 1, skipped_count: 0 } },
        recovery: { restored_task_count: 2, checkpoint_completed_layers: 1, checkpoint_age_seconds: 1.25 },
      }),
    })
    await clickTab(user, 'RUNS')
    const item = (await screen.findAllByText('run-b'))[0].closest('.run-history-item') as HTMLElement
    await user.click(within(item).getByRole('button', { name: /FAILED CHECKPOINT/ }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/workflows/runs/run-b'))).toBe(true))
    expect(await screen.findByText('SELECTED RUN')).toBeInTheDocument()
    expect(screen.getByText(/3 completed · 1 failed · 0 skipped/)).toBeInTheDocument()
    expect(screen.getByText(/RECOVERY · 2 tasks restored · 1 layers saved/)).toBeInTheDocument()
    expect(screen.getByText(/CHECKPOINT AGE · 1.250 seconds/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'CLOSE DETAILS' }))
    expect(screen.queryByText('SELECTED RUN')).not.toBeInTheDocument()
  })

  it('RESUME CHECKPOINT posts to the real replay endpoint and refreshes history', async () => {
    let gate: Promise<Response> = Promise.resolve(json({ run_id: 'run-new', status: 'completed' }))
    const { calls, user } = setupApp({
      'GET /api/workflows/runs': () => json({ runs }),
      'POST /api/workflows/runs/:id/resume': url => {
        expect(url.pathname).toBe('/api/workflows/runs/run-b/resume')
        return gate
      },
    })
    await clickTab(user, 'RUNS')
    const item = (await screen.findAllByText('run-b'))[0].closest('.run-history-item') as HTMLElement
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(within(item).getByRole('button', { name: 'RESUME CHECKPOINT' }))
    await waitFor(() => expect(calls.some(call => call.method === 'POST' && call.url.endsWith('/api/workflows/runs/run-b/resume'))).toBe(true))
    expect(screen.getAllByRole('button', { name: 'RESUMING…' }).every(button => (button as HTMLButtonElement).disabled)).toBe(true)
    resolve(json({ run_id: 'run-new', status: 'completed' }))
    await waitFor(() => expect(screen.queryAllByRole('button', { name: 'RESUMING…' })).toHaveLength(0))
    expect(within(item).getByRole('button', { name: 'RESUME CHECKPOINT' })).toBeEnabled()
  })
})
