const configuredBase = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const API_BASE = configuredBase.replace(/\/$/, '')

function readCookie(name: string): string | undefined {
  const prefix = `${name}=`
  const part = document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(prefix))
  if (!part) return undefined
  try {
    return decodeURIComponent(part.slice(prefix.length))
  } catch {
    return undefined
  }
}

/** Same-origin cookie client with automatic CSRF headers for state changes. */
export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = readCookie('market_mind_csrf')
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  const response = await fetch(input, {
    ...init,
    headers,
    credentials: 'include',
  })
  const requestUrl = String(input)
  if (response.status === 401 && !requestUrl.includes('/api/auth/login')) {
    window.dispatchEvent(new Event('market-mind-auth-expired'))
  }
  return response
}
