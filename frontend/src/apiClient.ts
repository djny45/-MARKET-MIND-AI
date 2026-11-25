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
  // Protocol-relative URLs (//evil.example) start with '/' but resolve to a
  // different origin; never attach the CSRF token to them.
  if (reference.startsWith('//')) return false
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

/** The API origin, when the frontend is served from a different origin.
 *  Requests to this origin (or to the current origin) carry the session cookie. */
function configuredApiOrigin(): string {
  const raw = (import.meta.env.VITE_API_URL ?? '').trim()
  if (!raw) return globalThis.location?.origin ?? ''
  try {
    return new URL(raw, globalThis.location?.origin || undefined).origin
  } catch {
    return ''
  }
}

function isApiRequest(input: RequestInfo | URL): boolean {
  const reference = typeof input === 'string' || input instanceof URL
    ? String(input)
    : input.url
  if (reference.startsWith('//')) return false
  const origin = globalThis.location?.origin
  if (!origin) return false
  try {
    const target = new URL(reference, origin)
    return target.origin === origin || target.origin === configuredApiOrigin()
  } catch {
    return false
  }
}

/** Fetch wrapper for authenticated research API calls.
 *
 * The session cookie is HttpOnly; cross-origin requests do not send it unless
 * `credentials: 'include'` is set. Only requests to the configured API origin
 * (or same-origin) opt in — arbitrary external URLs never receive credentials.
 * An explicit caller-provided `credentials` value is always respected.
 */
export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const credentials = init?.credentials ?? (isApiRequest(input) ? 'include' : undefined)
  return globalThis.fetch(input, credentials ? { ...init, credentials } : init)
}

/** Install once at application startup. Returns a restore function for tests. */
export function installCsrfFetch(): () => void {
  const original = globalThis.fetch
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    original(input, withCsrf(input, init))) as typeof fetch
  return () => { globalThis.fetch = original }
}
