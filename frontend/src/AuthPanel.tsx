import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, LogIn, LogOut, ShieldCheck, UserRound } from 'lucide-react'
import { apiFetch } from './apiClient'

export type Identity = { username: string; role: string }

type Props = {
  api: string
  onIdentity?: (identity: Identity | null) => void
}

type SessionState = 'loading' | 'disabled' | 'anonymous' | 'expired' | 'authenticated' | 'error'

function readCookie(name: string): string {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

/**
 * Per-user session UI backed by the existing /api/auth endpoints.
 * It never handles API keys, signing credentials or other backend secrets:
 * the session cookie is HttpOnly and the CSRF token is echoed from its cookie.
 */
export default function AuthPanel({ api, onIdentity }: Props) {
  const [state, setState] = useState<SessionState>('loading')
  const [user, setUser] = useState<Identity | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [actionFailed, setActionFailed] = useState(false)

  const publish = (identity: Identity | null) => {
    setUser(identity)
    onIdentity?.(identity)
  }

  const load = async () => {
    setState('loading')
    try {
      const response = await apiFetch(`${api}/api/auth/me`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (response.status === 401) {
        publish(null)
        setState('expired')
        setMessage('Session expired or unauthorized. Sign in again to continue.')
        return
      }
      if (!response.ok) throw new Error(body.detail || 'Session status unavailable')
      if (!body.enabled) {
        publish(null)
        setState('disabled')
        setMessage('')
        return
      }
      const identity: Identity | null = body.user ?? null
      publish(identity)
      setState(identity ? 'authenticated' : 'anonymous')
      setMessage('')
    } catch (error) {
      publish(null)
      setState('error')
      setMessage(error instanceof Error ? error.message : 'Session status unavailable')
    }
  }

  useEffect(() => { void load() }, [api])

  const login = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    setActionFailed(false)
    try {
      const response = await apiFetch(`${api}/api/auth/login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Login failed')
      publish({ username: body.username, role: body.role })
      setState('authenticated')
      setPassword('')
      setMessage('SIGNED IN')
    } catch (error) {
      setActionFailed(true)
      setMessage(error instanceof Error ? error.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  const logout = async () => {
    setBusy(true)
    setMessage('')
    setActionFailed(false)
    try {
      const response = await apiFetch(`${api}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': readCookie('mm_csrf') },
      })
      if (!response.ok) throw new Error('Logout failed')
      publish(null)
      setState('anonymous')
      setMessage('SIGNED OUT')
    } catch (error) {
      setActionFailed(true)
      setMessage(error instanceof Error ? error.message : 'Logout failed')
    } finally {
      setBusy(false)
    }
  }

  const showForm = state === 'anonymous' || state === 'expired'

  return (
    <section className="auth-panel" aria-label="User authentication">
      <div className="auth-heading"><ShieldCheck size={14} /> <b>USER AUTHENTICATION</b></div>
      {state === 'loading' && <small role="status">CHECKING SESSION…</small>}
      {state === 'disabled' && <small>Per-user authentication is disabled. Local research mode only; enable MARKET_MIND_USER_AUTH before remote exposure.</small>}
      {state === 'error' && <small className="news-error" role="alert">{message}</small>}
      {state === 'expired' && <small className="news-error" role="alert"><AlertTriangle size={13} /> {message}</small>}
      {state === 'authenticated' && user && (
        <div className="auth-identity">
          <span><UserRound size={14} /> <b>{user.username}</b> · {user.role.toUpperCase()}</span>
          <button type="button" className="soft-btn" onClick={logout} disabled={busy}>
            <LogOut size={13} />{busy ? 'SIGNING OUT…' : 'SIGN OUT'}
          </button>
        </div>
      )}
      {showForm && (
        <form onSubmit={login} className="auth-form" role="form" aria-label="Sign in form">
          <label htmlFor="auth-username">SIGN IN FOR SCOPED RESEARCH ACTIONS</label>
          <input id="auth-username" aria-label="Username" autoComplete="username"
            value={username} onChange={event => setUsername(event.target.value)} placeholder="username" />
          <input id="auth-password" aria-label="Password" type="password" autoComplete="current-password"
            value={password} onChange={event => setPassword(event.target.value)} placeholder="password" />
          <button type="submit" className="run-btn" disabled={busy || !username.trim() || !password}>
            <LogIn size={13} />{busy ? 'SIGNING IN…' : 'SIGN IN'}
          </button>
        </form>
      )}
      {actionFailed && <small className="news-error" role="alert">{message}</small>}
      {message && !actionFailed && state !== 'error' && state !== 'expired' && (
        <small aria-live="polite">{message}</small>
      )}
    </section>
  )
}
