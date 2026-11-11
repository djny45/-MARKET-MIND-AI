import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import AuthGate from './AuthGate'
import { apiFetch } from './api'

vi.mock('./api', () => ({
  API_BASE: '',
  apiFetch: vi.fn(),
}))

const mockedApiFetch = vi.mocked(apiFetch)
const ok = () => ({ ok: true, status: 200, json: async () => ({}) }) as Response
const failure = (status: number, detail: string) => ({
  ok: false,
  status,
  json: async () => ({ detail }),
}) as Response

describe('AuthGate', () => {
  beforeEach(() => {
    mockedApiFetch.mockReset()
    mockedApiFetch.mockResolvedValue(ok())
  })

  afterEach(() => cleanup())

  it('shows the private workspace after the session is verified', async () => {
    render(<AuthGate><div>Private workspace</div></AuthGate>)
    expect(await screen.findByText('Private workspace')).toBeTruthy()
    expect(mockedApiFetch).toHaveBeenCalledWith('/api/auth/session')
  })

  it('keeps the workspace visible when server-side logout fails', async () => {
    mockedApiFetch.mockImplementation(async (input) => {
      if (String(input).endsWith('/session')) return ok()
      return failure(503, 'Authentication storage unavailable')
    })
    render(<AuthGate><div>Private workspace</div></AuthGate>)
    await screen.findByText('Private workspace')
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Authentication storage unavailable')
    expect(screen.getByText('Private workspace')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy()
  })

  it('returns to sign-in only after logout succeeds', async () => {
    mockedApiFetch.mockResolvedValue(ok())
    render(<AuthGate><div>Private workspace</div></AuthGate>)
    await screen.findByText('Private workspace')
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Owner sign in' })).toBeTruthy()
    expect(screen.queryByText('Private workspace')).toBeNull()
  })
})
