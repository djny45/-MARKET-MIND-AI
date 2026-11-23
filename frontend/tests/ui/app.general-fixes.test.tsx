import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

describe('App general UI fixes', () => {
  it('the Help button opens an accessible dialog that can be closed', async () => {
    const { user } = setupApp()
    await user.click(screen.getByRole('button', { name: 'Help' }))
    const dialog = await screen.findByRole('dialog', { name: /HELP/ })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveTextContent(/SCREENER/)
    expect(dialog).toHaveTextContent(/no execution layer/i)
    await user.click(screen.getByRole('button', { name: /Close help/ }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('shows a busy state and an error when watchlist refresh fails', async () => {
    let resolveSecond!: (value: Response) => void
    const secondCall = new Promise<Response>(res => { resolveSecond = res })
    let calls = 0
    const { user } = setupApp({
      'GET /api/watchlist': () => ++calls === 1 ? json({ symbols: [] }) : secondCall,
    })
    await clickTab(user, 'WATCHLIST')
    const button = await screen.findByRole('button', { name: 'REFRESH WATCHLIST' })
    await user.click(button)
    expect(screen.getByRole('button', { name: 'REFRESHING…' })).toBeDisabled()
    resolveSecond(json({ detail: 'watchlist offline' }, 503))
    expect(await screen.findByRole('alert')).toHaveTextContent('watchlist offline')
    expect(screen.getByRole('button', { name: 'REFRESH WATCHLIST' })).toBeEnabled()
  })

  it('hides privileged navigation for a viewer', async () => {
    setupApp({ 'GET /api/auth/me': () => json({ enabled: true, user: { username: 'v', role: 'viewer' } }) })
    await waitFor(() => expect(screen.queryByRole('button', { name: 'RUNS' })).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'OVERVIEW' })).toBeInTheDocument()
  })

  it('shows privileged navigation for an operator', async () => {
    setupApp({ 'GET /api/auth/me': () => json({ enabled: true, user: { username: 'o', role: 'operator' } }) })
    expect(await screen.findByRole('button', { name: 'RUNS' })).toBeInTheDocument()
  })

  it('exposes the stored-observation screener and heatmap tabs', async () => {
    const { user } = setupApp()
    await clickTab(user, 'SCREENER')
    expect((await screen.findAllByRole('region', { name: 'Research observation screener' })).length).toBeGreaterThan(0)
    await clickTab(user, 'COVERAGE')
    expect((await screen.findAllByRole('region', { name: 'Stored observation coverage heatmap' })).length).toBeGreaterThan(0)
  })
})
