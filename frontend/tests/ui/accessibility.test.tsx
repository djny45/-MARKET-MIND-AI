import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { axe, toHaveNoViolations } from 'jest-axe'
import PriceChart from '../../src/PriceChart'
import { clickTab, setupAgentNetwork, setupAgentPositions, setupApp, setupLearningLab, setupUi } from './helpers'

expect.extend(toHaveNoViolations)

// jsdom does not apply the external stylesheet, so pixel contrast cannot be
// evaluated here. Structural rules, roles, names and keyboard semantics are.
const axeOptions = { rules: { 'color-contrast': { enabled: false } } } as any

async function expectAccessible(container: HTMLElement, label: string) {
  const results = await axe(container, axeOptions)
  if (results.violations.length) {
    console.error(`${label} violations:`, results.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target) })))
  }
  expect(results.violations, `${label} should have no axe violations`).toHaveLength(0)
}

const agents = [
  { id: 'worker_001', name: 'Data Sentinel', department: 'validation', specialty: 'Quality', status: 'REGISTERED' },
]

describe('Accessibility (jest-axe)', () => {
  it('dashboard overview has no structural accessibility violations', async () => {
    const view = setupApp()
    await screen.findByRole('heading', { name: 'Market research overview' })
    await expectAccessible(view.container, 'Dashboard overview')
  })

  it('validation view labels its payload editor and controls', async () => {
    const { user, container } = setupApp()
    await clickTab(user, 'DATA VALIDATION')
    expect(screen.getByRole('textbox', { name: 'Payload JSON' })).toBeInTheDocument()
    await expectAccessible(container, 'Validation view')
  })

  it('research view labels all form controls', async () => {
    const { user, container } = setupApp()
    await clickTab(user, 'RESEARCH')
    expect(screen.getByRole('textbox', { name: 'Historical OHLCV CSV' })).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: 'Regression threshold' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'CSV source label' })).toBeInTheDocument()
    await expectAccessible(container, 'Research view')
  })

  it('agent network exposes labelled filters', async () => {
    const view = setupAgentNetwork(agents)
    await screen.findByRole('textbox', { name: 'Search agent network' })
    expect(screen.getByRole('combobox', { name: 'Filter by department' })).toBeInTheDocument()
    await expectAccessible(view.container, 'Agent network')
  })

  it('agent position monitor exposes labelled filters and a data table', async () => {
    const view = setupAgentPositions(agents)
    await screen.findByRole('textbox', { name: 'Search agent positions' })
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Filter by stance' })).toBeInTheDocument()
    await expectAccessible(view.container, 'Agent position monitor')
  })

  it('learning lab exposes labelled inputs', async () => {
    const view = setupLearningLab(agents)
    await screen.findByRole('textbox', { name: 'Reviewer notes' })
    expect(screen.getByRole('textbox', { name: 'Filter learning agents' })).toBeInTheDocument()
    await expectAccessible(view.container, 'Learning lab')
  })

  it('chart exposes non-text status text and a labelled host region', async () => {
    const view = setupUi(<PriceChart bars={[{ timestamp: '2026-01-01T00:00:00Z', open: 1, high: 2, low: 0, close: 1.5, volume: 10, source: 'csv', status: 'historical' }]} />)
    expect(screen.getByText('STORED OHLCV HISTORY')).toBeInTheDocument()
    await expectAccessible(view.container, 'Price chart')
  })

  it('keyboard operation: tabbing reaches the primary research controls and Enter triggers them', async () => {
    const { user } = setupApp()
    await clickTab(user, 'DATA VALIDATION')
    const button = screen.getByRole('button', { name: 'LOAD SAMPLE' })
    button.focus()
    expect(button).toHaveFocus()
    await user.keyboard('{Enter}')
    expect((screen.getByRole('textbox', { name: 'Payload JSON' }) as HTMLTextAreaElement).value).toContain('"symbol": "BTCUSD"')
  })
})
