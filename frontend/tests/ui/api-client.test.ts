import { afterEach, describe, expect, it, vi } from 'vitest'
import { CSRF_HEADER, apiFetch, installCsrfFetch, readCsrfCookie, withCsrf } from '../../src/apiClient'

const cookie = 'other=1; mm_csrf=token-123; theme=dark'

describe('central CSRF wiring', () => {
  it('reads only the session CSRF cookie', () => {
    expect(readCsrfCookie(cookie)).toBe('token-123')
    expect(readCsrfCookie('other=1')).toBe('')
  })

  it('adds the header to same-origin writes only', () => {
    const post = withCsrf('/api/watchlist', { method: 'POST' }, cookie)
    expect(new Headers(post.headers).get(CSRF_HEADER)).toBe('token-123')
    expect(withCsrf('/api/watchlist', { method: 'GET' }, cookie).headers).toBeUndefined()

    const external = withCsrf('https://example.invalid/api', { method: 'POST' }, cookie)
    expect(new Headers(external.headers).get(CSRF_HEADER)).toBeNull()
    const protocolRelative = withCsrf('//example.invalid/api', { method: 'POST' }, cookie)
    expect(new Headers(protocolRelative.headers).get(CSRF_HEADER)).toBeNull()
    const absoluteSameOrigin = withCsrf(
      `${globalThis.location.origin}/api/watchlist`, { method: 'POST' }, cookie)
    expect(new Headers(absoluteSameOrigin.headers).get(CSRF_HEADER)).toBe('token-123')
  })

  it('never overrides an explicit token', () => {
    const init = withCsrf('/api/watchlist', {
      method: 'POST', headers: { [CSRF_HEADER]: 'explicit' },
    }, cookie)
    expect(new Headers(init.headers).get(CSRF_HEADER)).toBe('explicit')
  })

  it('wraps global fetch and restores the original', () => {
    const original = globalThis.fetch
    document.cookie = 'mm_csrf=cookie-token'
    const spy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(null, { status: 204 }))
    globalThis.fetch = spy as typeof fetch
    const restore = installCsrfFetch()
    void globalThis.fetch('/api/watchlist', { method: 'POST' })
    const [url, options] = spy.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/watchlist')
    expect(new Headers(options.headers).get(CSRF_HEADER)).toBe('cookie-token')
    restore()
    expect(globalThis.fetch).toBe(spy)
    globalThis.fetch = original
  })
})

describe('apiFetch session credentials', () => {
  it('sends the session cookie to the configured cross-origin API', async () => {
    vi.stubEnv('VITE_API_URL', 'http://127.0.0.1:18090')
    const spy = vi.fn(async () => new Response(null, { status: 200 }))
    globalThis.fetch = spy as typeof fetch
    await apiFetch('http://127.0.0.1:18090/api/workers?limit=550')
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit]
    expect(init.credentials).toBe('include')
  })

  it('sends the session cookie for same-origin relative URLs', async () => {
    const spy = vi.fn(async () => new Response(null, { status: 200 }))
    globalThis.fetch = spy as typeof fetch
    await apiFetch('/api/health')
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit]
    expect(init.credentials).toBe('include')
  })

  it('does not send credentials to an unrelated external origin', async () => {
    vi.stubEnv('VITE_API_URL', 'http://127.0.0.1:18090')
    const spy = vi.fn(async () => new Response(null, { status: 200 }))
    globalThis.fetch = spy as typeof fetch
    await apiFetch('https://example.invalid/data')
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit | undefined]
    expect(init?.credentials).toBeUndefined()
  })

  it('preserves an explicit credentials setting', async () => {
    vi.stubEnv('VITE_API_URL', 'http://127.0.0.1:18090')
    const spy = vi.fn(async () => new Response(null, { status: 200 }))
    globalThis.fetch = spy as typeof fetch
    await apiFetch('http://127.0.0.1:18090/api/health', { credentials: 'omit' })
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit]
    expect(init.credentials).toBe('omit')
  })
})
