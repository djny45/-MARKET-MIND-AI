import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

describe('Operations modules', () => {
  it('portfolio research computes historical performance from the backend', async () => {
    const { user, calls } = setupApp({
      'POST /api/analytics/performance': () => json({
        observations: 5, cumulative_return: 0.05, max_drawdown: -0.01,
        annualized_volatility: 0.2, annualized_sharpe: 1.1, sortino_per_period: 0.8,
        scope: 'Historical descriptive statistics; not a forecast or recommendation.',
      }),
    })
    await clickTab(user, 'PORTFOLIO')
    expect(await screen.findByText(/Historical descriptive statistics only/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'CALCULATE' }))
    expect(await screen.findByText(/CUMULATIVE RETURN/)).toBeInTheDocument()
    expect(calls.some(c => c.url.endsWith('/api/analytics/performance') && c.method === 'POST')).toBe(true)
  })

  it('risk analytics reports drawdown and volatility without inventing returns', async () => {
    const { user } = setupApp({
      'POST /api/analytics/performance': () => json({
        cumulative_return: 0, max_drawdown: -0.25, annualized_volatility: 0.3,
        annualized_sharpe: null, sortino_per_period: null,
      }),
    })
    await clickTab(user, 'RISK')
    await user.click(screen.getByRole('button', { name: 'CALCULATE' }))
    expect(await screen.findByText(/MAX DRAWDOWN/)).toBeInTheDocument()
    expect(screen.getByText(/-25.00%/)).toBeInTheDocument()
  })

  it('system health and provider health show server-reported status', async () => {
    const { user } = setupApp({
      'GET /api/health': () => json({ status: 'ok', service: 'market-mind-ai', broker_execution: false, paper_trading: false }),
      'GET /api/ready': () => json({ status: 'ready' }),
      'GET /api/analytical-agent-supervisor/status': () => json({ status: 'idle', status_counts: { queued: 2 } }),
      'GET /api/providers/status': () => json({
        status: 'no_live_provider_configured', live_providers: [],
        available_adapters: [{ name: 'synthetic-fixture', status: 'available', data_status: 'synthetic', purpose: 'development only' }],
        market_data_note: 'No live or delayed market-data provider is currently configured.',
      }),
    })
    await clickTab(user, 'SYSTEM HEALTH')
    expect(await screen.findByText(/BROKER EXECUTION FALSE/)).toBeInTheDocument()
    await clickTab(user, 'PROVIDERS')
    expect(await screen.findByText(/no_live_provider_configured/)).toBeInTheDocument()
    expect(screen.getByText(/No live or delayed market-data provider/)).toBeInTheDocument()
  })

  it('audit and backup panels surface errors for insufficient roles', async () => {
    const { user } = setupApp({
      'GET /api/security/audit-events': () => json({ detail: 'Insufficient role' }, 403),
      'GET /api/backup/status': () => json({ detail: 'Insufficient role' }, 403),
    })
    await clickTab(user, 'AUDIT')
    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient role')
    await clickTab(user, 'BACKUP')
    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient role')
  })

  it('settings shows only non-secret configuration from the backend', async () => {
    const { user } = setupApp({
      'GET /api/system/config': () => json({ checks: { secure_cookies: true, trusted_proxy_count: 1 } }),
      'GET /api/environment-validation': () => json({ checks: { strict_mode: true } }),
    })
    await clickTab(user, 'SETTINGS')
    expect(await screen.findByText(/NO SECRETS/)).toBeInTheDocument()
    expect(screen.getByText(/secure_cookies/)).toBeInTheDocument()
  })

  it('locks audit, backup and settings for viewer roles', async () => {
    const { user } = setupApp({
      'GET /api/auth/me': () => json({ enabled: true, user: { username: 'v', role: 'viewer' } }),
    })
    for (const name of ['AUDIT', 'BACKUP', 'SETTINGS']) {
      const button = await screen.findByRole('button', { name })
      expect(button).toHaveAttribute('aria-disabled', 'true')
      await user.click(button)
    }
    expect(await screen.findByRole('alert')).toHaveTextContent(/requires (OPERATOR|ADMIN) role or higher/)
  })
})
