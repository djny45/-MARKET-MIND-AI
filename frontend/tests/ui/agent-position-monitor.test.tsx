import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { setupAgentPositions } from './helpers'

const agents = Array.from({ length: 60 }, (_, i) => ({
  id: `agent-${String(i + 1).padStart(3, '0')}`,
  name: `Analyst ${i + 1}`,
  department: i % 2 === 0 ? 'technical_research' : 'validation',
  specialty: i % 2 === 0 ? 'Momentum' : 'Quality',
  status: 'REGISTERED',
}))

describe('AgentPositionMonitor component', () => {
  it('renders the research-only stance board and the first 50 profiles', async () => {
    setupAgentPositions(agents)
    expect(await screen.findByRole('heading', { name: /AI Agent Position Monitor/ })).toBeInTheDocument()
    expect(screen.getByText(/Research stance board only/)).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(51) // header + 50 rows
    expect(screen.getByRole('button', { name: /LOAD NEXT 50 PROFILES/ })).toBeInTheDocument()
    expect(screen.getByText(/Profiles shown: 60/)).toBeInTheDocument()
  })

  it('assigning a stance updates the row badge, the summary count and the filtered view', async () => {
    const { user } = setupAgentPositions(agents)
    const row = await screen.findByRole('row', { name: /Analyst 1 agent-001/ })
    expect(within(row).getByText(/NOT TAGGED/)).toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: 'LONG' }))

    expect(within(row).getByText('LONG', { selector: '.stance-badge' })).toBeInTheDocument()
    const longSummary = screen.getByRole('button', { name: /1 LONG \/ BULLISH/ })
    await user.click(longSummary)
    expect(screen.getAllByRole('row')).toHaveLength(2) // header + the one tagged row
    await user.click(screen.getByRole('button', { name: /1 LONG \/ BULLISH/ }))
    expect(screen.getAllByRole('row').length).toBeGreaterThan(2)
  })

  it('search, department and stance selects filter the table and RESET clears everything', async () => {
    const { user } = setupAgentPositions(agents.slice(0, 4))
    const search = await screen.findByRole('textbox', { name: 'Search agent positions' })
    await user.type(search, 'Analyst 3')
    expect(screen.getAllByRole('row')).toHaveLength(2)

    await user.clear(search)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by department' }), 'validation')
    expect(screen.getByText(/2 matching profiles/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /TAG FILTERED NEUTRAL/ }))
    expect(screen.getByRole('button', { name: /2 NEUTRAL/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /RESET/ }))
    expect(screen.getByText(/4 matching profiles/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /0 NEUTRAL/ })).toBeInTheDocument()
    expect((search as HTMLInputElement).value).toBe('')
  })

  it('LOAD NEXT 50 PROFILES reveals more rows; row selection and inspector stance control work', async () => {
    const { user } = setupAgentPositions(agents)
    expect(screen.getAllByRole('row')).toHaveLength(51)
    await user.click(await screen.findByRole('button', { name: /LOAD NEXT 50 PROFILES/ }))
    expect(screen.getAllByRole('row')).toHaveLength(61)

    const row = screen.getByRole('row', { name: /Analyst 55 agent-055/ })
    await user.click(row)
    const inspector = await screen.findByRole('complementary')
    expect(inspector).toHaveTextContent('Analyst 55')
    await user.selectOptions(within(inspector).getByRole('combobox'), 'SHORT')
    expect(within(screen.getByRole('row', { name: /Analyst 55 agent-055/ })).getByText('SHORT', { selector: '.stance-badge' })).toBeInTheDocument()
    await user.click(within(inspector).getByRole('button', { name: 'CLOSE' }))
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })

  it('instrument selection changes the stance column label and every summary control has an effect', async () => {
    const { user } = setupAgentPositions(agents.slice(0, 2))
    await user.selectOptions(screen.getByRole('combobox', { name: 'INSTRUMENT' }), 'ETHUSD')
    expect(screen.getByText('RESEARCH STANCE · ETHUSD')).toBeInTheDocument()

    const short = screen.getByRole('button', { name: /SHORT \/ BEARISH/ })
    await user.click(short)
    expect(screen.getByText(/0 matching profiles/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /SHORT \/ BEARISH/ }))
    expect(screen.getByText(/2 matching profiles/)).toBeInTheDocument()
  })
})
