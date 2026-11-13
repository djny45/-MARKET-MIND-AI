import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AgentPositionMonitor from './AgentPositionMonitor'

describe('AgentPositionMonitor', () => {
  it('keeps manual research stance labels separate for each instrument', () => {
    render(<AgentPositionMonitor agents={[{
      id: 'worker_001',
      name: 'Historical Analyst',
      department: 'Research',
      specialty: 'Historical data',
      status: 'REGISTERED',
    }]} />)

    const instrument = screen.getByLabelText('INSTRUMENT')
    const row = screen.getByText('worker_001').closest('tr')
    expect(row).not.toBeNull()

    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: 'LONG', exact: true }))
    expect(row?.querySelector('.stance-badge')?.textContent).toBe('LONG')

    fireEvent.change(instrument, { target: { value: 'ETHUSD' } })
    expect(row?.querySelector('.stance-badge')?.textContent).toBe('— NOT TAGGED')
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: 'SHORT', exact: true }))
    expect(row?.querySelector('.stance-badge')?.textContent).toBe('SHORT')

    fireEvent.change(instrument, { target: { value: 'BTCUSD' } })
    expect(row?.querySelector('.stance-badge')?.textContent).toBe('LONG')

    fireEvent.change(instrument, { target: { value: 'ETHUSD' } })
    expect(row?.querySelector('.stance-badge')?.textContent).toBe('SHORT')
  })
})
