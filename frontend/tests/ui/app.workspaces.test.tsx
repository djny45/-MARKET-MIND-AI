import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { bodyOf, clickTab, json, setupApp, type FetchCall } from './helpers'

describe('App / saved layouts (workspaces)', () => {
  it('SAVE GRAPH posts the current title, nodes and edges, then refreshes the workspace list', async () => {
    const saved: { id: string; title: string }[] = []
    const { user, calls } = setupApp({
      'GET /api/workspaces': () => json({ workflows: saved }),
      'POST /api/workspaces': (_url, init) => {
        const entry = { id: 'ws-1', title: bodyOf(init).title }
        saved.push(entry)
        return json(entry)
      },
    })
    await clickTab(user, 'WORKFLOW')
    const title = screen.getByRole('textbox', { name: 'Workspace name' })
    await user.clear(title)
    await user.type(title, 'Phase 2 layout')

    await user.click(screen.getByRole('button', { name: 'SAVE GRAPH' }))
    await waitFor(() => expect(calls.some(call => call.method === 'POST' && call.url.endsWith('/api/workspaces'))).toBe(true))
    const post = calls.find(call => call.method === 'POST' && call.url.endsWith('/api/workspaces')) as FetchCall
    const payload = bodyOf(post.init)
    expect(payload.title).toBe('Phase 2 layout')
    expect(payload.description).toBe('Saved visual research graph')
    expect(payload.nodes).toHaveLength(6)
    expect(payload.edges).toHaveLength(6)
    expect(calls.filter(call => call.url.endsWith('/api/workspaces') && call.method === 'GET').length).toBeGreaterThanOrEqual(2)

    expect(await screen.findByText('EXECUTION INSPECTOR')).toBeInTheDocument()
    expect(screen.getByText(/"status": "saved"/)).toBeInTheDocument()
    expect(within(screen.getByRole('combobox', { name: 'Load saved workspace' })).getByRole('option', { name: 'Phase 2 layout' })).toBeInTheDocument()
  })

  it('SAVE GRAPH exposes a SAVING… busy state', async () => {
    let gate: Promise<Response> = Promise.resolve(json({ id: 'ws-1', title: 'ok' }))
    const { user } = setupApp({ 'POST /api/workspaces': () => gate })
    await clickTab(user, 'WORKFLOW')
    let resolve!: (value: Response) => void
    gate = new Promise<Response>(res => { resolve = res })
    await user.click(screen.getByRole('button', { name: 'SAVE GRAPH' }))
    expect(screen.getByRole('button', { name: 'SAVING…' })).toBeDisabled()
    resolve(json({ id: 'ws-1', title: 'ok' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'SAVE GRAPH' })).toBeEnabled())
  })

  it('a failed save is reported in the execution inspector', async () => {
    const { user } = setupApp({ 'POST /api/workspaces': () => json({ detail: 'save denied' }, 500) })
    await clickTab(user, 'WORKFLOW')
    await user.click(screen.getByRole('button', { name: 'SAVE GRAPH' }))
    expect(await screen.findByText(/"status": "error"/)).toBeInTheDocument()
    expect(screen.getByText(/save denied/)).toBeInTheDocument()
  })

  it('LOAD WORKSPACE restores nodes, edges and title from the selected saved layout', async () => {
    const { user, calls } = setupApp({
      'GET /api/workspaces': () => json({ workflows: [{ id: 'layout-7', title: 'Historical layout' }] }),
      'GET /api/workspaces/:id': url => {
        expect(url.pathname).toBe('/api/workspaces/layout-7')
        return json({
          id: 'layout-7', title: 'Historical layout',
          nodes: [
            { id: 'restored-1', type: 'market', position: { x: 0, y: 0 }, data: { label: 'Restored feed', category: 'data' } },
            { id: 'restored-2', type: 'output', position: { x: 100, y: 0 }, data: { label: 'Restored report', category: 'output' } },
          ],
          edges: [{ id: 're', source: 'restored-1', target: 'restored-2' }],
        })
      },
    })
    await clickTab(user, 'WORKFLOW')
    const select = await screen.findByRole('combobox', { name: 'Load saved workspace' })
    await user.selectOptions(select, 'layout-7')

    await waitFor(() => expect(calls.some(call => call.url.endsWith('/api/workspaces/layout-7'))).toBe(true))
    expect(screen.getByRole('textbox', { name: 'Workspace name' })).toHaveValue('Historical layout')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-node-count', '2')
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-edge-count', '1')
    expect(screen.getByTestId('flow-node-restored-1')).toHaveTextContent('Restored feed')
    expect(screen.getByText(/"status": "loaded"/)).toBeInTheDocument()
  })

  it('a failed workspace load is reported in the execution inspector', async () => {
    const { user } = setupApp({
      'GET /api/workspaces': () => json({ workflows: [{ id: 'bad', title: 'Broken layout' }] }),
      'GET /api/workspaces/:id': () => json({ detail: 'layout missing' }, 404),
    })
    await clickTab(user, 'WORKFLOW')
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Load saved workspace' }), 'bad')
    expect(await screen.findByText(/"status": "error"/)).toBeInTheDocument()
    expect(screen.getByText(/layout missing/)).toBeInTheDocument()
  })
})
