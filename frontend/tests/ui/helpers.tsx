import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ReactElement } from 'react'
import App from '../../src/App'
import AgentNetwork from '../../src/AgentNetwork'
import AgentPositionMonitor from '../../src/AgentPositionMonitor'
import LearningLab from '../../src/LearningLab'

export const API = 'http://localhost:8000'

export type RouteHandler = (url: URL, init?: RequestInit) => Response | Promise<Response>
export type FetchCall = { url: string; method: string; init?: RequestInit }

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function bodyOf(init?: RequestInit): any {
  if (!init?.body) return {}
  try {
    return typeof init.body === 'string' ? JSON.parse(init.body) : {}
  } catch {
    return {}
  }
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

type Route = { method: string | null; regex: RegExp; handler: RouteHandler }

function compileRoute(key: string, handler: RouteHandler): Route {
  const match = key.trim().match(/^([A-Z]+)\s+(\S.*)$/)
  const method = match ? match[1] : null
  const pattern = match ? match[2] : key.trim()
  const escaped = pattern
    .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*')
    .replace(/:[A-Za-z_]\w*/g, '[^/]+')
  return { method, regex: new RegExp(`^${escaped}$`), handler }
}

const defaultRoutes: Record<string, RouteHandler> = {
  'GET /api/health': () => json({ status: 'ok', worker_count: 550 }),
  'GET /api/workers': () => json({ workers: [] }),
  'GET /api/skills': () => json({ skills: [] }),
  'GET /api/workspaces': () => json({ workflows: [] }),
  'POST /api/workspaces': (_url, init) => {
    const body = bodyOf(init)
    return json({ id: 'ws-1', title: body.title || 'Untitled workspace', nodes: body.nodes || [], edges: body.edges || [] })
  },
  'GET /api/workspaces/:id': () => json({ id: 'ws-1', title: 'Restored workspace', nodes: [], edges: [] }),
  'GET /api/watchlist': () => json({ symbols: [] }),
  'POST /api/watchlist': (_url, init) => json({ symbol: bodyOf(init).symbol, already_present: false }),
  'DELETE /api/watchlist/:symbol': () => json({ removed: true }),
  'GET /api/workflows/runs': () => json({ runs: [] }),
  'GET /api/workflows/runs/:id': () => json({ id: 'run-1', status: 'completed', created_at: '2026-01-01T00:00:00Z', result: {} }),
  'POST /api/workflows/runs/:id/resume': () => json({ run_id: 'run-2', status: 'completed' }),
  'POST /api/workflows/execute': () => json({ status: 'completed', run_id: 'run-exec-1', tasks: [] }),
  'GET /api/market-data/overview': () => json({ instrument_interval_count: 0, coverage: [], data_note: 'fixture: stored data only' }),
  'GET /api/market-data/history': () => json({
    bars: [], source: 'fixture', status: 'historical', retrieved_at: '2026-01-01T00:00:00Z',
    source_count: 1, timestamp_count: 0, duplicate_timestamp_observations: 0,
    first_timestamp: null, last_timestamp: null, sources: [],
  }),
  'GET /api/research/data-quality': () => json({
    symbol: 'BTCUSD', interval: '1h', bars_checked: 2,
    timestamp_spacing: { status: 'ok', spacing_anomaly_count: 0, expected_interval_seconds: 3600, spacing_anomalies: [] },
    timestamp_integrity: { invalid_timestamp_count: 0, duplicate_timestamp_count: 0, out_of_order_count: 0, invalid_timestamps: [], duplicate_timestamps: [], out_of_order_timestamps: [] },
    close_to_close_return_outliers: { status: 'ok', flagged_bar_indices: [], flagged_observations: [] },
    volume_outliers: { status: 'ok', flagged_bar_indices: [], flagged_observations: [] },
  }),
  'GET /api/research/timeline': () => json({ events: [] }),
  'GET /api/news': () => json({ items: [] }),
  'GET /api/auth/me': () => json({ enabled: false, user: null }),
  'GET /api/agent-network/activity': () => json({ task_count: 0, status_counts: {}, latest_by_agent: {}, note: 'fixture' }),
  'GET /api/analytical-agents/learning-overview': () => json({
    agent_count: 0, agents: [], agents_with_feedback: 0, total_feedback_records: 0,
    scored_feedback_records: 0, unverified_feedback_records: 0, improvement_proposals: 0,
    system_feedback_score: null, score_note: 'fixture: descriptive only',
  }),
  'POST /api/analytical-agents/:id/learning-feedback': () => json({ memory_id: 'mem-1' }),
}

/** Installs a fetch double with sensible fixture responses for every endpoint the app calls on mount. */
export function mockFetch(routes: Record<string, RouteHandler> = {}) {
  const calls: FetchCall[] = []
  const table = [
    ...Object.entries(routes).map(([key, handler]) => compileRoute(key, handler)),
    ...Object.entries(defaultRoutes).map(([key, handler]) => compileRoute(key, handler)),
  ]
  const fetchMock = vi.fn(async (input: any, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const rawMethod = init?.method ?? (input && typeof input !== 'string' && 'method' in input ? (input as Request).method : 'GET')
    const method = String(rawMethod).toUpperCase()
    calls.push({ url, method, init })
    const parsed = new URL(url, API)
    const path = parsed.pathname.replace(/\/+$/, '') || '/'
    const route = table.find(entry => (!entry.method || entry.method === method) && entry.regex.test(path))
    if (route) return route.handler(parsed, init)
    return json({}, 200)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

export function setupUi(ui: ReactElement, routes: Record<string, RouteHandler> = {}) {
  const network = mockFetch(routes)
  const user = userEvent.setup()
  const view = render(ui)
  return { ...network, user, ...view }
}

export function setupApp(routes: Record<string, RouteHandler> = {}) {
  return setupUi(<App />, routes)
}

export function setupAgentNetwork(agents: any[] = [], routes: Record<string, RouteHandler> = {}) {
  return setupUi(<AgentNetwork agents={agents} />, routes)
}

export function setupAgentPositions(agents: any[] = [], routes: Record<string, RouteHandler> = {}) {
  return setupUi(<AgentPositionMonitor agents={agents} />, routes)
}

export function setupLearningLab(agents: any[] = [], routes: Record<string, RouteHandler> = {}) {
  return setupUi(<LearningLab api={API} agents={agents} />, routes)
}

export async function clickTab(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole('button', { name: new RegExp(`^${name}$`) }))
}
