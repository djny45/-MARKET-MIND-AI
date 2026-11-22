import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { bodyOf, json, setupLearningLab } from './helpers'

const agents = [
  { id: 'worker_001', name: 'Data Sentinel' },
  { id: 'worker_002', name: 'Trend Analyst' },
]
const overview = {
  agent_count: 2, agents_with_feedback: 1, total_feedback_records: 5,
  scored_feedback_records: 3, unverified_feedback_records: 2, improvement_proposals: 1,
  system_feedback_score: 0.8, score_note: 'descriptive score only',
  agents: [
    { worker_id: 'worker_001', feedback_count: 5, scored_feedback_count: 3, observed_feedback_score: 0.8, improvement_proposals: 1, evaluation_status: 'evaluated', feedback_outcomes: {} },
    { worker_id: 'worker_002', feedback_count: 0, scored_feedback_count: 0, observed_feedback_score: null, improvement_proposals: 0, evaluation_status: 'no_feedback', feedback_outcomes: {} },
  ],
}

describe('LearningLab component', () => {
  it('loads the overview, renders stats and agent feedback list, and filters by agent id', async () => {
    const { user } = setupLearningLab(agents, { 'GET /api/analytical-agents/learning-overview': () => json(overview) })
    expect(await screen.findByRole('heading', { name: /Agent Learning Lab/ })).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getAllByText('5').length).toBeGreaterThan(0)
    expect(screen.getByText('80.0%')).toBeInTheDocument()
    expect(screen.getAllByText(/descriptive score only/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Data Sentinel.*5 feedback/ })).toBeInTheDocument()

    const filter = await screen.findByRole('textbox', { name: 'Filter learning agents' })
    await user.type(filter, 'worker_002')
    expect(screen.getByRole('button', { name: /Trend Analyst/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Data Sentinel.*5 feedback/ })).not.toBeInTheDocument()
  })

  it('shows an error when the overview request rejects and REFRESH retries it', async () => {
    let succeed = false
    const { user, calls } = setupLearningLab(agents, {
      'GET /api/analytical-agents/learning-overview': () => succeed ? json(overview) : Promise.reject(new Error('learning offline')),
    })
    expect(await screen.findByText('learning offline')).toBeInTheDocument()
    succeed = true
    await user.click(screen.getByRole('button', { name: /REFRESH LEARNING DATA/ }))
    await waitFor(() => expect(calls.filter(call => call.url.includes('/api/analytical-agents/learning-overview')).length).toBeGreaterThanOrEqual(2))
    expect(await screen.findByText(/descriptive score only/)).toBeInTheDocument()
  })

  it('SAVE REVIEW FEEDBACK posts the chosen agent/outcome/notes and reloads the overview', async () => {
    const { user, calls } = setupLearningLab(agents, {
      'GET /api/analytical-agents/learning-overview': () => json(overview),
      'POST /api/analytical-agents/:id/learning-feedback': (url, init) => {
        expect(url.pathname).toBe('/api/analytical-agents/worker_002/learning-feedback')
        expect(bodyOf(init)).toEqual({ summary: 'Accurate historical context', outcome: 'partially_helpful', metrics: {} })
        return json({ memory_id: 'mem-42' })
      },
    })
    await screen.findByText(/descriptive score only/)
    const save = screen.getByRole('button', { name: /SAVE REVIEW FEEDBACK/ })
    expect(save).toBeDisabled()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Agent' }), 'worker_002')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Assessment' }), 'partially_helpful')
    await user.type(screen.getByRole('textbox', { name: 'Reviewer notes' }), 'Accurate historical context')
    expect(save).toBeEnabled()
    await user.click(save)

    await waitFor(() => expect(calls.some(call => call.method === 'POST' && call.url.includes('/learning-feedback'))).toBe(true))
    expect(await screen.findByText('FEEDBACK RECORDED · mem-42')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Reviewer notes' })).toHaveValue('')
    expect(calls.filter(call => call.url.includes('/learning-overview')).length).toBeGreaterThanOrEqual(2)
  })

  it('feedback API errors are shown without claiming success', async () => {
    const { user } = setupLearningLab(agents, {
      'POST /api/analytical-agents/:id/learning-feedback': () => json({ detail: 'feedback rejected' }, 400),
    })
    await user.type(await screen.findByRole('textbox', { name: 'Reviewer notes' }), 'notes')
    await user.click(screen.getByRole('button', { name: /SAVE REVIEW FEEDBACK/ }))
    expect(await screen.findByText('feedback rejected')).toBeInTheDocument()
  })

  it('learning controls state the governance guard and every control is reachable', async () => {
    const { user } = setupLearningLab(agents)
    expect(await screen.findByText(/No autonomous model-weight training/)).toBeInTheDocument()
    expect(within(screen.getByRole('button', { name: /REFRESH LEARNING DATA/ })).getByText(/REFRESH LEARNING DATA/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /REFRESH LEARNING DATA/ }))
    expect(await screen.findByText(/Model training: OFF/)).toBeInTheDocument()
  })
})
