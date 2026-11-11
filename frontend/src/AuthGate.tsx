import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { API_BASE, apiFetch } from './api'

type AuthGateProps = { children: ReactNode }

export default function AuthGate({ children }: AuthGateProps) {
  const [status, setStatus] = useState<'checking' | 'signed-out' | 'signed-in' | 'setup-required'>('checking')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    apiFetch(`${API_BASE}/api/auth/session`)
      .then(async response => {
        if (!active) return
        if (response.ok) {
          setStatus('signed-in')
          return
        }
        if (response.status === 401) {
          setStatus('signed-out')
          return
        }
        if (response.status === 503) {
          setStatus('setup-required')
          setError('Owner authentication is not configured on the backend.')
          return
        }
        setStatus('signed-out')
        setError('Unable to verify the current session. Please sign in again.')
      })
      .catch(() => {
        if (active) {
          setStatus('setup-required')
          setError('Cannot reach the authentication service.')
        }
      })
    return () => { active = false }
  }, [])

  async function signOut() {
    try {
      await apiFetch(`${API_BASE}/api/auth/logout`, { method: 'POST' })
    } finally {
      setStatus('signed-out')
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await apiFetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        if (response.status === 503) setStatus('setup-required')
        throw new Error(payload.detail || 'Sign in failed')
      }
      setPassword('')
      setStatus('signed-in')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  if (status === 'signed-in') return <><div className="auth-session-control"><button type="button" onClick={signOut}>Sign out</button></div>{children}</>
  if (status === 'checking') {
    return <main className="auth-shell"><section className="auth-card"><div className="auth-mark">MM</div><p className="auth-eyebrow">MARKET-MIND-AI</p><h1>Checking secure session</h1><p className="auth-muted">Verifying your private workspace access…</p></section></main>
  }
  if (status === 'setup-required') {
    return <main className="auth-shell"><section className="auth-card"><div className="auth-mark">MM</div><p className="auth-eyebrow">PRIVATE RESEARCH WORKSPACE</p><h1>Authentication setup required</h1><p className="auth-muted">{error || 'Configure the owner password hash on the backend before signing in.'}</p><p className="auth-help">Generate a hash with <code>python create_owner_hash.py</code> from the backend directory, then set <code>MARKET_MIND_OWNER_PASSWORD_HASH</code> and restart the service.</p></section></main>
  }
  return <main className="auth-shell"><section className="auth-card">
    <div className="auth-mark">MM</div>
    <p className="auth-eyebrow">PRIVATE RESEARCH WORKSPACE</p>
    <h1>Owner sign in</h1>
    <p className="auth-muted">Authenticate to access your market research terminal.</p>
    <form className="auth-form" onSubmit={submit}>
      <label htmlFor="owner-password">Owner password</label>
      <input id="owner-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={1024} autoFocus />
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !password}>{busy ? 'Verifying…' : 'Sign in securely'}</button>
    </form>
    <p className="auth-help">Session cookies are HttpOnly. Workspace changes require CSRF validation.</p>
  </section></main>
}
