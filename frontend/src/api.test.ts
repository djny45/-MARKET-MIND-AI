import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from './api'

describe('apiFetch', () => {
  beforeEach(() => {
    document.cookie = 'market_mind_csrf=csrf%20token; path=/'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.cookie = 'market_mind_csrf=; Max-Age=0; path=/'
  })

  it('includes cookies and adds the CSRF header to state-changing requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/watchlist', { method: 'POST' })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.credentials).toBe('include')
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf token')
  })

  it('does not add a CSRF header to safe GET requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/health')

    const [, init] = fetchMock.mock.calls[0]
    expect(init.credentials).toBe('include')
    expect(new Headers(init.headers).has('X-CSRF-Token')).toBe(false)
  })

  it('dispatches the session-expired event for protected API 401 responses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    const expired = vi.fn()
    window.addEventListener('market-mind-auth-expired', expired)

    await apiFetch('/api/watchlist')

    expect(expired).toHaveBeenCalledOnce()
    window.removeEventListener('market-mind-auth-expired', expired)
  })

  it('does not dispatch session expiry for a login 401 response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    const expired = vi.fn()
    window.addEventListener('market-mind-auth-expired', expired)

    await apiFetch('/api/auth/login', { method: 'POST' })

    expect(expired).not.toHaveBeenCalled()
    window.removeEventListener('market-mind-auth-expired', expired)
  })
})
