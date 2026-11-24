import { afterEach, describe, expect, it, vi } from 'vitest'
import { CSRF_HEADER, installCsrfFetch, readCsrfCookie, withCsrf } from '../../src/apiClient'

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
