import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { clickTab, json, setupApp } from './helpers'

const items = [
  { id: 'n1', title: 'Official exchange notice', url: 'https://example.org/notice', source: 'exchange', published_at: '2026-01-01T00:00:00Z' },
  { id: 'n2', title: 'Regulator publication', url: 'https://example.org/regulator', source: 'regulator', published_at: '2026-01-02T00:00:00Z' },
]

describe('App / news intelligence', () => {
  it('FETCH OFFICIAL NEWS renders source-linked headlines with a busy state', async () => {
    let gate: Promise<Response> = Promise.resolve(json({ items }))
    const { calls, user } = setupApp({ 'GET /api/news': () => gate })
    await clickTab(user, 'NEWS')
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(screen.getByRole('button', { name: 'FETCH OFFICIAL NEWS' }))
    expect(screen.getByRole('button', { name: 'FETCHING…' })).toBeDisabled()
    resolve(json({ items }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/news'))).toBe(true))

    const links = await screen.findAllByRole('link')
    const newsLink = links.find(link => link.textContent?.includes('Official exchange notice')) as HTMLElement
    expect(newsLink).toHaveAttribute('href', 'https://example.org/notice')
    expect(newsLink).toHaveAttribute('target', '_blank')
    expect(within(newsLink).getByText(/exchange · 2026-01-01/)).toBeInTheDocument()
    expect(screen.getByText(/Regulator publication/)).toBeInTheDocument()
  })

  it('renders per-source errors returned inside a successful news response', async () => {
    const { user } = setupApp({
      'GET /api/news': () => json({ items: [{ id: 'e1', source: 'feed-a', error: 'timeout' }, ...items] }),
    })
    await clickTab(user, 'NEWS')
    await user.click(screen.getByRole('button', { name: 'FETCH OFFICIAL NEWS' }))
    expect(await screen.findByText('feed-a: timeout')).toBeInTheDocument()
    expect(screen.getByText('Official exchange notice')).toBeInTheDocument()
  })

  it('shows a top-level error when the news request rejects at the network layer', async () => {
    const { user } = setupApp({ 'GET /api/news': () => Promise.reject(new Error('network refused')) })
    await clickTab(user, 'NEWS')
    await user.click(screen.getByRole('button', { name: 'FETCH OFFICIAL NEWS' }))
    expect(await screen.findByText('network refused')).toBeInTheDocument()
  })

  it('DOCUMENTED GAP: a non-2xx news response with a detail field does not surface an error', async () => {
    const { user } = setupApp({ 'GET /api/news': () => json({ detail: 'news offline' }, 503) })
    await clickTab(user, 'NEWS')
    await user.click(screen.getByRole('button', { name: 'FETCH OFFICIAL NEWS' }))
    expect(await screen.findByRole('button', { name: 'FETCH OFFICIAL NEWS' })).toBeEnabled()
    expect(screen.queryByText('news offline')).not.toBeInTheDocument()
  })
})
