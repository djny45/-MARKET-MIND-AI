import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { clickTab, setupApp } from './helpers'

describe('UI test harness smoke check', () => {
  it('renders the real App with mocked fetch and the flow doubles', async () => {
    const { user } = setupApp()
    expect(await screen.findByText('Market research overview')).toBeInTheDocument()
    await clickTab(user, 'WORKFLOW')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '6')
  })
})
