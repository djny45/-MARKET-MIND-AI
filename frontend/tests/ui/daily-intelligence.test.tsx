import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const archive = [
  { cycle_id: 'daily-2026-11-26', cycle_date: '2026-11-26', market_group: 'us',
    revision: 1, content_sha256: 'abcdef1234567890', parent_sha256: null,
    created_at: '2026-11-26T12:00:00Z' },
]

const cycle = {
  cycle_id: 'daily-2026-11-26', cycle_date: '2026-11-26', status: 'partial',
  generated_at: '2026-11-26T12:00:00Z', duplicate_cycle_detected: false,
  observations: [
    { market_group: 'us', data_status: 'historical', status_label: 'HISTORICAL',
      headline: 'FRESH', usable_count: 5, unavailable_count: 0, stale_count: 0,
      source: 'yahoo-us-equities' },
    { market_group: 'gold', data_status: 'unavailable', status_label: 'UNAVAILABLE',
      headline: 'PROVIDER UNAVAILABLE', usable_count: 0, unavailable_count: 1,
      stale_count: 0, reason: 'provider unavailable (HTTPError)' },
  ],
  execution: {
    registered_agents: 550, agents_assigned_tasks: 4, agents_executed_tasks: 2,
    agents_completed_tasks: 1, agents_failed: 1, agents_skipped: 0,
    concurrent_execution_count: 4, tasks_completed: 3, tasks_pending: 1,
    metric_definition: '550 registered profiles are NOT 550 active models or independent processes.',
  },
  quality_scorecard: {
    observation_coverage: 0.8333, usable_observations: 5,
    unavailable_observations: 1, stale_observations: 0,
    agent_participation: 0.0036, data_labels_verified: true,
    scorecard_note: 'Descriptive process metrics only.',
  },
  consensus: { available: true, disagreement_present: false },
  zulip_notification: { status: 'sent' },
  archive: { archived: [] },
}

const ROUTES = {
  'GET /api/daily/archive': () => json({ count: 1, rows: archive }),
  'POST /api/daily/run': () => json(cycle),
}

describe('Daily Intelligence panel', () => {
  it('runs a cycle and shows honest agent accountability', async () => {
    const { user, calls } = setupApp(ROUTES)
    await clickTab(user, 'DAILY INTELLIGENCE')
    const panel = await screen.findByRole('region', { name: 'Daily intelligence research cycle' })

    await user.click(within(panel).getByRole('button', { name: 'RUN DAILY CYCLE' }))
    expect(await within(panel).findByText('PARTIAL')).toBeInTheDocument()
    expect(within(panel).getByText('REGISTERED 550')).toBeInTheDocument()
    expect(within(panel).getByText('EXECUTED 2')).toBeInTheDocument()
    expect(within(panel).getByText(/NOT 550 active models/)).toBeInTheDocument()
    expect(calls.some(c => c.url.includes('/api/daily/run') && c.method === 'POST')).toBe(true)
  })

  it('shows verified labels and unavailable data clearly', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'DAILY INTELLIGENCE')
    const panel = await screen.findByRole('region', { name: 'Daily intelligence research cycle' })
    await user.click(within(panel).getByRole('button', { name: 'RUN DAILY CYCLE' }))

    expect(await within(panel).findByText('HISTORICAL')).toBeInTheDocument()
    expect(within(panel).getByText('UNAVAILABLE')).toBeInTheDocument()
    expect(within(panel).getByText('LABELS VERIFIED TRUE')).toBeInTheDocument()
    expect(within(panel).getByText(/provider unavailable/)).toBeInTheDocument()
  })

  it('shows the append-only archive', async () => {
    const { user } = setupApp(ROUTES)
    await clickTab(user, 'DAILY INTELLIGENCE')
    const panel = await screen.findByRole('region', { name: 'Daily intelligence research cycle' })

    expect(await within(panel).findByText(/DAILY RESEARCH ARCHIVE/)).toBeInTheDocument()
    expect(within(panel).getByText(/No previous report is overwritten/)).toBeInTheDocument()
  })

  it('surfaces a failed cycle without claiming success', async () => {
    const { user } = setupApp({
      ...ROUTES,
      'POST /api/daily/run': () => json({ detail: 'cycle provider unavailable' }, 502),
    })
    await clickTab(user, 'DAILY INTELLIGENCE')
    const panel = await screen.findByRole('region', { name: 'Daily intelligence research cycle' })
    await user.click(within(panel).getByRole('button', { name: 'RUN DAILY CYCLE' }))

    expect(await within(panel).findByRole('alert')).toHaveTextContent('cycle provider unavailable')
    expect(within(panel).queryByText('REGISTERED 550')).not.toBeInTheDocument()
  })
})
