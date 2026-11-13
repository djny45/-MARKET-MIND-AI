import { useEffect, useMemo, useState } from 'react'
import { BrainCircuit, RefreshCw, Send, ShieldCheck } from 'lucide-react'
import { apiFetch } from './api'

type LearningAgent = {
  worker_id: string
  feedback_count: number
  scored_feedback_count: number
  observed_feedback_score: number | null
  improvement_proposals: number
  evaluation_status: string
  feedback_outcomes: Record<string, number>
}
type Props = { api: string; agents: { id: string; name?: string }[] }

export default function LearningLab({ api, agents }: Props) {
  const [overview, setOverview] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [agentId, setAgentId] = useState('worker_001')
  const [outcome, setOutcome] = useState('helpful')
  const [summary, setSummary] = useState('')
  const [feedbackBusy, setFeedbackBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [query, setQuery] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try {
      const response = await apiFetch(api + '/api/analytical-agents/learning-overview')
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Learning overview unavailable')
      setOverview(data)
    } catch (e) { setError(e instanceof Error ? e.message : 'Learning overview unavailable') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [api])
  const filtered = useMemo(() => (overview?.agents || []).filter((a: LearningAgent) =>
    [a.worker_id, agents.find(x => x.id === a.worker_id)?.name || ''].join(' ').toLowerCase().includes(query.toLowerCase())
  ).slice(0, 100), [overview, agents, query])

  const submitFeedback = async () => {
    setFeedbackBusy(true); setMessage('')
    try {
      const response = await apiFetch(api + '/api/analytical-agents/' + encodeURIComponent(agentId) + '/learning-feedback', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary, outcome, metrics: {} })
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not save feedback')
      setMessage('FEEDBACK RECORDED · ' + data.memory_id)
      setSummary('')
      await load()
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Feedback submission failed') }
    finally { setFeedbackBusy(false) }
  }

  return <section className="learning-lab">
    <header className="learning-heading">
      <div><span className="eyebrow">MARKET-MIND-AI / GOVERNED IMPROVEMENT</span><h1><BrainCircuit size={22}/> Agent Learning Lab</h1>
      <p>Collect reviewer feedback, inspect improvement proposals, and evaluate agent quality over time.</p></div>
      <button className="soft-btn" onClick={load} disabled={loading}><RefreshCw size={14}/>{loading ? 'REFRESHING…' : 'REFRESH LEARNING DATA'}</button>
    </header>
    <div className="learning-guard"><ShieldCheck size={16}/> Learning is feedback-driven and human-reviewed. No autonomous model-weight training or automatic strategy updates are enabled.</div>
    {error && <div className="news-error">{error}</div>}
    <div className="learning-stats">
      <article><small>REGISTERED AGENTS</small><strong>{overview?.agent_count ?? '—'}</strong></article>
      <article><small>AGENTS WITH FEEDBACK</small><strong>{overview?.agents_with_feedback ?? '—'}</strong></article>
      <article><small>REVIEWER FEEDBACK</small><strong>{overview?.total_feedback_records ?? '—'}</strong><small>{overview?.scored_feedback_records ?? 0} scored · {overview?.unverified_feedback_records ?? 0} unverified</small></article>
      <article><small>IMPROVEMENT PROPOSALS</small><strong>{overview?.improvement_proposals ?? '—'}</strong></article>
      <article><small>FEEDBACK SCORE · DESCRIPTIVE</small><strong>{overview?.system_feedback_score == null ? 'N/A' : (overview.system_feedback_score * 100).toFixed(1) + '%'}</strong></article>
    </div>
    <div className="learning-columns">
      <div className="learning-panel">
        <div className="overview-panel-head"><div><b>FEEDBACK BY AGENT</b><small>Reviewer ratings, not strategy profitability</small></div></div>
        <input className="learning-search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Filter agent IDs…" />
        <div className="learning-list">{filtered.map((a: LearningAgent) => <button key={a.worker_id} className={agentId===a.worker_id?'learning-agent active':'learning-agent'} onClick={()=>setAgentId(a.worker_id)}>
          <span><b>{agents.find(x=>x.id===a.worker_id)?.name || a.worker_id}</b><small>{a.worker_id} · {a.evaluation_status.replace(/_/g,' ')}</small></span>
          <span><strong>{a.feedback_count}</strong><small>feedback</small></span><span><strong>{a.improvement_proposals}</strong><small>proposals</small></span>
        </button>)}</div>
        <small className="learning-note">Showing up to 100 of 550 agents. Feedback summaries use the latest stored records per agent.</small>
      </div>
      <div className="learning-panel">
        <b>SUBMIT REVIEW FEEDBACK</b><small>Agent: {agentId} · use feedback from a completed research task</small>
        <label>Agent<select value={agentId} onChange={e=>setAgentId(e.target.value)}>{agents.slice(0,550).map(a=><option key={a.id} value={a.id}>{a.id} · {a.name || a.id}</option>)}</select></label>
        <label>Assessment<select value={outcome} onChange={e=>setOutcome(e.target.value)}><option value="helpful">Helpful</option><option value="partially_helpful">Partially helpful</option><option value="not_helpful">Not helpful</option><option value="unverified">Unverified</option></select></label>
        <label>Reviewer notes<textarea value={summary} onChange={e=>setSummary(e.target.value)} placeholder="What was accurate, missing, or should be improved?" maxLength={4000}/></label>
        <button className="run-btn" onClick={submitFeedback} disabled={feedbackBusy || !summary.trim()}><Send size={14}/>{feedbackBusy?'SAVING…':'SAVE REVIEW FEEDBACK'}</button>
        {message && <small className="learning-note">{message}</small>}
        <div className="learning-note">Saved feedback is evidence for future review. It does not change the model or agent configuration automatically.</div>
      </div>
    </div>
    <footer className="learning-note">{overview?.score_note || 'Feedback is descriptive only.'} · Model training: OFF · Auto-apply: OFF</footer>
  </section>
}
