import { useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
type Action = 'help' | 'version'

export default function OpenBBTerminal() {
 const [action, setAction] = useState<Action>('help')
 const [output, setOutput] = useState('')
 const [error, setError] = useState('')
 const [busy, setBusy] = useState(false)
 const [installed, setInstalled] = useState<boolean | null>(null)
 const [enabled, setEnabled] = useState<boolean | null>(null)

 async function checkStatus() {
  setError('')
  try {
   const response = await fetch(`${API}/api/openbb/status`)
   if (!response.ok) throw new Error(`API returned ${response.status}`)
   const data = await response.json()
   setInstalled(Boolean(data.installed))
   setEnabled(Boolean(data.enabled))
  } catch (e) {
   setInstalled(null)
   setEnabled(null)
   setError(e instanceof Error ? e.message : 'Could not reach backend')
  }
 }

 async function runCommand() {
  setBusy(true); setError(''); setOutput('')
  try {
   const response = await fetch(`${API}/api/openbb/cli`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
   })
   if (!response.ok) throw new Error(`API returned ${response.status}`)
   const data = await response.json()
   setOutput(data.output || '')
   if (data.error) setError(data.error)
   setInstalled(Boolean(data.available))
   if (!data.error) setEnabled(true)
   else if (data.error.includes('disabled')) setEnabled(false)
  } catch (e) {
   setError(e instanceof Error ? e.message : 'Could not reach backend')
  } finally { setBusy(false) }
 }

 return <section className="overview-area openbb-terminal">
  <div className="overview-heading"><div><span className="eyebrow">OPENBB / LOCAL CLI</span><h1>OpenBB terminal</h1><p>Restricted informational CLI bridge. This is not an unrestricted shell or an interactive REPL.</p></div><button className="soft-btn" onClick={checkStatus}>CHECK INSTALLATION</button></div>
  <div className="overview-status"><span className={installed===true?'status-ok':installed===false?'status-off':''}>{installed===true?'INSTALLED':installed===false?'NOT INSTALLED':'UNKNOWN'}</span><span>OPENBB CLI</span><span className="overview-separator">·</span><span className={enabled===true?'status-ok':enabled===false?'status-off':''}>{enabled===true?'EXECUTION ENABLED':enabled===false?'EXECUTION DISABLED':'EXECUTION STATUS UNKNOWN'}</span><span className="overview-separator">·</span><span>ALLOWLISTED COMMANDS ONLY</span></div>
  <div className="overview-panel openbb-controls">
   <label htmlFor="openbb-action">COMMAND</label>
   <select id="openbb-action" value={action} onChange={e=>setAction(e.target.value as Action)}><option value="help">openbb --help</option><option value="version">OpenBB CLI version (package metadata)</option></select>
   <button className="run-btn" onClick={runCommand} disabled={busy}>{busy?'RUNNING…':'RUN COMMAND'}</button>
  </div>
  {error && <p className="news-error">{error}</p>}
  <div className="overview-panel"><div className="overview-panel-head"><b>CLI OUTPUT</b><small>Local backend response</small></div><pre className="openbb-output">{output || 'Select a command and run it. Install OpenBB CLI and explicitly enable OPENBB_CLI_ENABLED=true in the trusted backend environment.'}</pre></div>
  <p className="overview-disclaimer">Safety: no raw shell input, no brokerage execution, and no interactive server-side REPL. For interactive OpenBB, use a local terminal with <code>openbb -i</code>.</p>
 </section>
}
