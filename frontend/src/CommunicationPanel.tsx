import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from './apiClient'

/** Optional communication status inbox.
 * Uses only existing backend status APIs. Never embeds Zulip credentials and
 * never rebuilds Zulip's messaging UI. The terminal remains usable offline.
 */
type Props = { api: string }

type CommStatus = {
  configured: boolean
  enabled: boolean
  pending_count: number
  sent_count: number
  last_successful_sync: string | null
  streams: Record<string, string[]>
  credentials_exposed: boolean
  inbound_commands_enabled: boolean
  broker_execution: boolean
  real_money: boolean
}

export default function CommunicationPanel({ api }: Props) {
  const [status, setStatus] = useState<CommStatus | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      const response = await apiFetch(`${api}/api/communication/status`, { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Status failed (${response.status})`)
      setStatus(body as CommStatus)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Communication status unavailable')
    } finally {
      setBusy(false)
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  return (
    <section className="comm-panel" aria-label="Optional communication status">
      <div className="comm-head">
        <div>
          <span className="eyebrow">MARKET-MIND-AI / COMMUNICATION LAYER</span>
          <h2>Zulip coordination (optional)</h2>
          <p>External notifications only. The existing agents, research engine and terminal remain authoritative and fully usable offline.</p>
        </div>
        <button type="button" className="soft-btn" onClick={() => void load()} disabled={busy}>
          {busy ? 'CHECKING…' : 'CHECK STATUS'}
        </button>
      </div>

      {error && <p className="news-error" role="alert">{error}</p>}
      {status && (
        <>
          <div className="comm-strip" role="status">
            <span className={`status-chip ${status.enabled ? 'status-ok' : 'status-off'}`}>
              {status.enabled ? 'CONNECTED' : status.configured ? 'DEGRADED' : 'NOT CONFIGURED'}
            </span>
            <span>PENDING {status.pending_count}</span>
            <span>SENT {status.sent_count}</span>
            <span>LAST SYNC {status.last_successful_sync || 'never'}</span>
            <span>CREDENTIALS EXPOSED {String(status.credentials_exposed).toUpperCase()}</span>
            <span>BROKER EXECUTION {String(status.broker_execution).toUpperCase()}</span>
          </div>
          <div className="comm-streams">
            {Object.entries(status.streams || {}).map(([name, topics]) => (
              <div key={name}>
                <b>{name.replace('-', ' ').toUpperCase()}</b>
                <small>{topics.join(' · ')}</small>
              </div>
            ))}
          </div>
          <p className="research-note">
            No chat commands are executed. Inbound messages never trigger research actions,
            orders or provider calls. Zulip outages cannot stop MARKET-MIND-AI.
          </p>
        </>
      )}
    </section>
  )
}
