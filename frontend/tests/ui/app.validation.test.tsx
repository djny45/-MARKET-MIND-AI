import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { bodyOf, clickTab, json, setupApp, type FetchCall } from './helpers'

describe('App / data validation view', () => {
  it('VALIDATE PAYLOAD posts the parsed JSON and renders a valid report', async () => {
    const { user, calls } = setupApp({
      'POST /api/market-data/validate': (_url, init) => {
        expect(bodyOf(init).payload.symbol).toBe('BTCUSD')
        return json({ valid: true, result: 'valid', error_count: 0, bar_count: 1, warnings: [] })
      },
    })
    await clickTab(user, 'DATA VALIDATION')
    expect(await screen.findByRole('heading', { name: 'Market data validation' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'VALIDATE PAYLOAD' }))
    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/market-data/validate'))).toBe(true))
    expect(await screen.findByText('VALID')).toBeInTheDocument()
    expect(screen.getByText('0 ERRORS')).toBeInTheDocument()
    expect(screen.getByText('1 BARS')).toBeInTheDocument()
    expect(screen.getByText('RAW VALIDATION REPORT')).toBeInTheDocument()
  })

  it('renders error details and warnings from an invalid payload report', async () => {
    const { user } = setupApp({
      'POST /api/market-data/validate': () => json({
        valid: false, result: 'invalid', error_count: 1, bar_count: 0,
        errors: [{ location: ['bars', 0, 'close'], message: 'must be positive' }],
        warnings: ['sparse timestamps'],
      }),
    })
    await clickTab(user, 'DATA VALIDATION')
    await user.click(await screen.findByRole('button', { name: 'VALIDATE PAYLOAD' }))
    expect(await screen.findByText('INVALID')).toBeInTheDocument()
    expect(screen.getByText('ERROR DETAILS')).toBeInTheDocument()
    expect(screen.getByText(/bars → 0 → close/)).toBeInTheDocument()
    expect(screen.getAllByText(/must be positive/).length).toBeGreaterThan(0)
    expect(screen.getByText('WARNINGS')).toBeInTheDocument()
    expect(screen.getByText('sparse timestamps')).toBeInTheDocument()
  })

  it('reports malformed JSON locally and surfaces API errors', async () => {
    const { user } = setupApp()
    await clickTab(user, 'DATA VALIDATION')
    const textarea = await screen.findByRole('textbox', { name: /payload json/i })
    await user.clear(textarea)
    await user.type(textarea, '{oops}')
    await user.click(screen.getByRole('button', { name: 'VALIDATE PAYLOAD' }))
    expect(await screen.findByText(/JSON|token/i, { selector: 'p.news-error' })).toBeInTheDocument()
  })

  it('LOAD SAMPLE replaces the payload with a one-bar example and clears prior results', async () => {
    const { user } = setupApp({
      'POST /api/market-data/validate': () => json({ valid: false, result: 'invalid', error_count: 1, errors: [], warnings: [] }),
    })
    await clickTab(user, 'DATA VALIDATION')
    const textarea = await screen.findByRole('textbox', { name: /payload json/i })
    await user.click(screen.getByRole('button', { name: 'VALIDATE PAYLOAD' }))
    expect(await screen.findByText('INVALID')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'LOAD SAMPLE' }))
    expect((textarea as HTMLTextAreaElement).value).toContain('"symbol": "BTCUSD"')
    expect((textarea as HTMLTextAreaElement).value).toContain('"bars"')
    expect(screen.queryByText('INVALID')).not.toBeInTheDocument()
  })

  it('VALIDATE PAYLOAD shows a busy state while the request is pending', async () => {
    let gate: Promise<Response> = Promise.resolve(json({ valid: true, result: 'valid' }))
    const { user } = setupApp({ 'POST /api/market-data/validate': () => gate })
    await clickTab(user, 'DATA VALIDATION')
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(await screen.findByRole('button', { name: 'VALIDATE PAYLOAD' }))
    expect(screen.getByRole('button', { name: 'VALIDATING…' })).toBeDisabled()
    resolve(json({ valid: true, result: 'valid' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'VALIDATE PAYLOAD' })).toBeEnabled())
  })

  it('the validation view states its structural-only limitation', async () => {
    const { user } = setupApp()
    await clickTab(user, 'DATA VALIDATION')
    expect(await screen.findByText(/Structural validation only/)).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('heading', { name: 'Market data validation' })).toBeInTheDocument()
  })
})
