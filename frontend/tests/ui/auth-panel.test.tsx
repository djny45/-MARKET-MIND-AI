import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import AuthPanel from '../../src/AuthPanel'
import { API, bodyOf, json, setupUi } from './helpers'

function setup(routes: Record<string, any> = {}, onIdentity = vi.fn()) {
  return {
    onIdentity,
    ...setupUi(<AuthPanel api={API} onIdentity={onIdentity} />, {
      'GET /api/auth/me': () => json({ enabled: true, user: null }),
      ...routes,
    }),
  }
}

describe('AuthPanel', () => {
  it('reports disabled per-user authentication without a sign-in form', async () => {
    setup({ 'GET /api/auth/me': () => json({ enabled: false, user: null }) })
    expect(await screen.findByText(/Per-user authentication is disabled/)).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Sign in form' })).not.toBeInTheDocument()
  })

  it('renders an accessible sign-in form for anonymous users', async () => {
    const { onIdentity } = setup()
    const form = await screen.findByRole('form', { name: 'Sign in form' })
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: /SIGN IN/ })).toBeDisabled()
    expect(onIdentity).toHaveBeenCalledWith(null)
    expect(form).toBeInTheDocument()
  })

  it('posts credentials and publishes the authenticated identity', async () => {
    const { user, calls, onIdentity } = setup({
      'GET /api/auth/me': () => json({ enabled: true, user: null }),
      'POST /api/auth/login': () => json({ username: 'analyst', role: 'analyst' }),
    })
    await screen.findByRole('form', { name: 'Sign in form' })
    await user.type(screen.getByLabelText('Username'), 'analyst')
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('button', { name: /SIGN IN/ }))
    const login = calls.find(call => call.url.endsWith('/api/auth/login'))
    expect(login?.method).toBe('POST')
    expect(login?.init?.credentials).toBe('include')
    expect(bodyOf(login?.init)).toEqual({ username: 'analyst', password: 'correct horse' })
    expect(await screen.findByText(/ANALYST/)).toBeInTheDocument()
    await waitFor(() => expect(onIdentity).toHaveBeenCalledWith({ username: 'analyst', role: 'analyst' }))
  })

  it('shows the backend error message on a failed sign-in', async () => {
    const { user } = setup({
      'GET /api/auth/me': () => json({ enabled: true, user: null }),
      'POST /api/auth/login': () => json({ detail: 'Invalid credentials' }, 401),
    })
    await screen.findByRole('form', { name: 'Sign in form' })
    await user.type(screen.getByLabelText('Username'), 'analyst')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: /SIGN IN/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials')
  })

  it('shows an expired-session state and allows re-authentication', async () => {
    setup({ 'GET /api/auth/me': () => json({ detail: 'Valid user session required.' }, 401) })
    expect(await screen.findByText(/Session expired or unauthorized/)).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Sign in form' })).toBeInTheDocument()
  })

  it('signs out with the CSRF token echoed from the cookie', async () => {
    document.cookie = 'mm_csrf=csrf-token-value'
    const { user, calls, onIdentity } = setup({
      'GET /api/auth/me': () => json({ enabled: true, user: { username: 'viewer', role: 'viewer' } }),
      'POST /api/auth/logout': () => json({ status: 'logged_out' }),
    })
    await screen.findByRole('button', { name: /SIGN OUT/ })
    await user.click(screen.getByRole('button', { name: /SIGN OUT/ }))
    const logout = calls.find(call => call.url.endsWith('/api/auth/logout'))
    expect(logout?.init?.headers).toMatchObject({ 'X-CSRF-Token': 'csrf-token-value' })
    expect(await screen.findByRole('form', { name: 'Sign in form' })).toBeInTheDocument()
    expect(onIdentity).toHaveBeenLastCalledWith(null)
    document.cookie = 'mm_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  })
})
