/** Same-origin CSRF wiring for the research terminal.

The session cookie is HttpOnly, but the CSRF token cookie is readable by the
browser by design. Attaching it centrally keeps every mutating fetch compliant
with the server's X-CSRF-Token check without duplicating headers at each call
site. No token is logged, stored in application state or sent cross-origin.
 */
export const CSRF_COOKIE = 'mm_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export function readCsrfCookie(cookie: string): string {
  for (const part of cookie.split(';')) {
    const separator = part.indexOf('=')
    if (separator < 0) continue
    if (part.slice(0, separator).trim() === CSRF_COOKIE) {
      return decodeURIComponent(part.slice(separator + 1).trim())
    }
  }
  return ''
}

function methodOf(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase()
  if (typeof Request !== 'undefined' && input instanceof Request) return input.method.toUpperCase()
  return 'GET'
}

function isSameOrigin(input: RequestInfo | URL): boolean {
  const reference = typeof input === 'string' || input instanceof URL
    ? String(input)
    : input.url
  if (reference.startsWith('/')) return true
  const origin = globalThis.location?.origin
  if (!origin) return false
  try {
    return new URL(reference, origin).origin === origin
  } catch {
    return false
  }
}

export function withCsrf(
  input: RequestInfo | URL,
  init?: RequestInit,
  cookie: string = typeof document === 'undefined' ? '' : document.cookie,
): RequestInit {
  if (!MUTATING_METHODS.has(methodOf(input, init)) || !isSameOrigin(input)) return init ?? {}
  const token = readCsrfCookie(cookie)
  if (!token) return init ?? {}
  const headers = new Headers(init?.headers)
  if (headers.has(CSRF_HEADER)) return init ?? {}
  headers.set(CSRF_HEADER, token)
  return { ...init, headers }
}

/** Install once at application startup. Returns a restore function for tests. */
export function installCsrfFetch(): () => void {
  const original = globalThis.fetch
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    original(input, withCsrf(input, init))) as typeof fetch
  return () => { globalThis.fetch = original }
}
