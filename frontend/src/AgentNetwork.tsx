import { useEffect, useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, type Node, type Edge } from '@xyflow/react'
import { Network, BrainCircuit } from 'lucide-react'
import GlobalResearchGlobe from './GlobalResearchGlobe'

type AgentProfile = {
  id?: string
  name?: string
  department?: string
  specialty?: string
  kind?: string
  status?: string
  memory_namespace?: string
}

type AgentNodeData = { label: string; department: string; specialty: string; status: string; core?: boolean; agentId?: string }
type ActivityEvent = { event_id: number; task_id: string; worker_id: string; event_type: string; from_status: string | null; to_status: string | null; occurred_at: string; detail: Record<string, unknown> }
type ActivitySnapshot = { task_count: number; status_counts: Record<string, number>; latest_by_agent: Record<string, { status: string; task_id: string; updated_at: string }>; recent_audit_events?: ActivityEvent[]; audit_event_count?: number; note?: string }
type AgentPerformance = { task_count: number; agents: Record<string, { task_count: number; queued: number; running: number; completed: number; failed: number; finished_count: number; completion_rate: number | null; failure_rate: number | null; execution_attempts_total: number; average_execution_attempts_per_task: number }>; performance_boundary: string }

function AgentNode({ data }: { data: AgentNodeData }) {
  return <div className={data.core ? 'agent-network-node core' : 'agent-network-node'}>
    <Handle type="target" position={Position.Left}/>
    <div className="agent-node-head"><span className="agent-node-dot"/><strong>{data.label}</strong></div>
    <div className="agent-node-department">{data.department}</div>
    <div className="agent-node-specialty">{data.specialty}</div>
    <div className="agent-node-foot"><span>{data.core ? 'SHARED INTELLIGENCE CORE' : 'REGISTERED AGENT PROFILE'}</span><span>{data.status}</span></div>
    <Handle type="source" position={Position.Right}/>
  </div>
}
const nodeTypes = { agent: AgentNode }

export default function AgentNetwork({ agents }: { agents: AgentProfile[] }) {
  const [query, setQuery] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('ALL DEPARTMENTS')
  const [selectedAgent, setSelectedAgent] = useState<AgentNodeData | null>(null)
  const [activity, setActivity] = useState<ActivitySnapshot | null>(null)
  const [activityError, setActivityError] = useState('')
  const [performance, setPerformance] = useState<AgentPerformance | null>(null)
  useEffect(() => { let alive = true; const load = async () => { try { const response = await fetch((import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/agent-network/activity?limit=500'); if (!response.ok) throw new Error('Activity endpoint unavailable'); const snapshot = await response.json(); const performanceResponse = await fetch((import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/agent-network/performance?limit=550'); if (!performanceResponse.ok) throw new Error('Performance endpoint unavailable'); const performanceSnapshot = await performanceResponse.json(); if (alive) { setActivity(snapshot); setPerformance(performanceSnapshot); setActivityError('') } } catch { if (alive) setActivityError('API activity unavailable — showing registered profiles only') } }; load(); const timer = window.setInterval(load, 20000); return () => { alive = false; window.clearInterval(timer) } }, [])
  const departments = useMemo(() => ['ALL DEPARTMENTS', ...Array.from(new Set(agents.map(a => a.department || 'General Research'))).sort()], [agents])
  const [eventFilter, setEventFilter] = useState('ALL EVENTS')
  const recentEvents = useMemo(() => (activity?.recent_audit_events || []).filter(event => eventFilter === 'ALL EVENTS' || (eventFilter === 'STATUS CHANGES' ? Boolean(event.from_status && event.to_status) : event.event_type.toUpperCase().includes(eventFilter))).slice(-12).reverse(), [activity, eventFilter])
  const filteredProfiles = useMemo(() => agents.slice(0, 550).filter(profile => {
    const haystack = [profile.id, profile.name, profile.department, profile.specialty, profile.kind].join(' ').toLowerCase()
    return haystack.includes(query.toLowerCase()) && (departmentFilter === 'ALL DEPARTMENTS' || (profile.department || 'General Research') === departmentFilter)
  }), [agents, query, departmentFilter])
  const { nodes, edges } = useMemo(() => {
    const profiles = filteredProfiles
    const centerX = 0, centerY = 0
    const radius = 850
    const nodes: Node<AgentNodeData>[] = [{
      id: 'intelligence-core',
      type: 'agent',
      position: { x: centerX, y: centerY },
      data: { label: 'MARKET-MIND AI', department: 'Central orchestration', specialty: 'Shared intelligence · evidence synthesis', status: 'CORE', core: true }
    }]
    const edges: Edge[] = []
    const departmentBuckets = new Map<string, string[]>()
    profiles.forEach((profile, index) => {
      const id = String(profile.id || `agent-${index + 1}`)
      const department = profile.department || 'General Research'
      const angle = (index / Math.max(profiles.length, 1)) * Math.PI * 2
      const ring = radius + (index % 4) * 105
      nodes.push({
        id,
        type: 'agent',
        position: { x: Math.cos(angle) * ring, y: Math.sin(angle) * ring },
        data: {
          label: profile.name || id,
          department,
          specialty: profile.specialty || profile.kind || 'Research specialization',
          status: activity?.latest_by_agent?.[id]?.status?.toUpperCase() || profile.status || 'PROFILE',
          agentId: id
        }
      })
      edges.push({ id: `core-${id}`, source: id, target: 'intelligence-core', style: { stroke: '#9c793d', strokeWidth: 0.65, opacity: 0.34 } })
      const bucket = departmentBuckets.get(department) || []
      bucket.push(id)
      departmentBuckets.set(department, bucket)
    })
    departmentBuckets.forEach((ids, department) => {
      ids.forEach((id, index) => {
        const next = ids[(index + 1) % ids.length]
        if (next && next !== id) edges.push({
          id: `dept-${department}-${id}-${next}`,
          source: id,
          target: next,
          style: { stroke: '#66869a', strokeWidth: 0.8, opacity: 0.28 }
        })
        if (ids.length > 3 && index % 3 === 0) {
          const cross = ids[(index + 3) % ids.length]
          if (cross && cross !== id) edges.push({
            id: `cross-${department}-${id}-${cross}`,
            source: id,
            target: cross,
            style: { stroke: '#7c6b9c', strokeWidth: 0.55, opacity: 0.18 }
          })
        }
      })
    })
    return { nodes, edges }
  }, [filteredProfiles, activity])

  return <motion.section className="agent-network-view" initial={{ opacity: 0, scale: 0.995 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.45, ease: "easeOut" }}>
    <div className="agent-network-heading">
      <div><span className="eyebrow">MARKET-MIND-AI / AGENT TOPOLOGY</span><h1><Network size={21}/> 550+ Analytical Agent Network</h1><p>Node-based visual map inspired by the reference image. Each card represents a registered specialist profile; the graph is a topology visualization, not proof that every agent is currently running.</p></div>
      <div className="agent-network-stats"><b>{agents.length || 550}</b><span>REGISTERED PROFILES</span><b>{edges.length.toLocaleString()}</b><span>VISUAL CONNECTIONS</span>{activity && <><b>{activity.status_counts.running || 0}</b><span>RUNNING TASKS</span><b>{activity.status_counts.queued || 0}</b><span>QUEUED TASKS</span></>}</div>
    </div>
    {activityError && <div className="agent-network-activity-note">{activityError}</div>}
    {activity && <div className="agent-network-activity-note">TASK ACTIVITY · {activity.task_count} persisted tasks · refreshes every 20 seconds · {activity.note}</div>}
    <GlobalResearchGlobe profileCount={agents.length || 550} activityCount={activity?.task_count || 0} />
    <div className="agent-network-legend"><span><i className="core-dot"/> Shared intelligence core</span><span><i className="dept-dot"/> Department links</span><span><i className="agent-dot"/> Agent profile → core</span><span><BrainCircuit size={13}/> Shared model architecture · no paper trading</span></div>
    {performance && <section className="agent-network-performance" aria-label="Persisted agent task performance">
      <div className="agent-network-performance-head"><div><span className="eyebrow">OPERATIONS / PERSISTED SQLITE</span><h2>Research task performance</h2><p>{performance.task_count} recorded tasks · descriptive operational metrics</p></div><span>NOT AN INTELLIGENCE SCORE</span></div>
      <div className="agent-network-performance-grid"><article><strong>{performance.task_count}</strong><small>TOTAL TASKS</small></article><article><strong>{Object.values(performance.agents).reduce((sum,item)=>sum+item.completed,0)}</strong><small>COMPLETED</small></article><article><strong>{Object.values(performance.agents).reduce((sum,item)=>sum+item.failed,0)}</strong><small>FAILED</small></article><article><strong>{Object.values(performance.agents).reduce((sum,item)=>sum+item.execution_attempts_total,0)}</strong><small>EXECUTION ATTEMPTS</small></article></div>
      <p className="agent-network-performance-note">{performance.performance_boundary}</p>
    </section>}
    {activity && <section className="agent-network-timeline" aria-label="Persisted agent task timeline">
      <div className="agent-network-timeline-head"><div><span className="eyebrow">AUDIT TRAIL / SQLITE</span><h2>Recent task events</h2><p>{activity.audit_event_count || 0} recorded events · newest first · bounded history</p></div>
        <label>EVENT FILTER<select value={eventFilter} onChange={e=>setEventFilter(e.target.value)}><option>ALL EVENTS</option><option>STATUS CHANGES</option><option>QUEUED</option><option>COMPLETED</option><option>FAILED</option></select></label>
      </div>
      {recentEvents.length ? <ol className="agent-network-timeline-list">{recentEvents.map(event=><li key={event.event_id}><span className="agent-timeline-marker"/><div><strong>{event.event_type.replace(/_/g," ").toUpperCase()}</strong><span>{event.worker_id} · {event.task_id}</span><small>{event.from_status && event.to_status ? event.from_status + " → " + event.to_status : event.to_status || "Recorded event"}</small></div><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></li>)}</ol> : <p className="agent-network-timeline-empty">No persisted events match this filter.</p>}
    </section>}
    <div className="agent-network-filterbar">
      <label className="agent-network-search"><Network size={14}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search agent name, specialty, department…" aria-label="Search agent network"/></label>
      <select value={departmentFilter} onChange={e=>setDepartmentFilter(e.target.value)} aria-label="Filter by department">{departments.map(department=><option key={department}>{department}</option>)}</select>
      <span>{filteredProfiles.length} / {agents.length || 550} profiles visible</span>
      <button type="button" onClick={()=>{setQuery("");setDepartmentFilter("ALL DEPARTMENTS");setSelectedAgent(null)}}>RESET FILTERS</button>
    </div>
    <div className="agent-network-canvas">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesFocusable edgesFocusable onSelectionChange={({ nodes: selectedNodes })=>setSelectedAgent(selectedNodes[0] ? selectedNodes[0].data as AgentNodeData : null)} fitView fitViewOptions={{ padding: 0.12, minZoom: 0.04, maxZoom: 1.1 }} minZoom={0.025} maxZoom={2} defaultEdgeOptions={{ animated: false }} nodesDraggable={false}>
        <Background color="#262b32" gap={22} size={1}/>
        <MiniMap nodeColor={n => n.id === 'intelligence-core' ? '#d4a34c' : '#607c98'} maskColor="rgba(5,8,12,.76)"/>
        <Controls/>
      </ReactFlow>
    </div>
    {selectedAgent && <motion.div className="agent-network-inspector" initial={{ opacity: 0, y: 10, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.22, ease: "easeOut" }}><div><b>{selectedAgent.label}</b><small>{selectedAgent.core ? "Central intelligence core" : selectedAgent.department}</small></div><span>{selectedAgent.specialty}</span><span className="agent-inspector-status">{selectedAgent.status}</span>{selectedAgent.agentId && (() => { const latest = activity?.latest_by_agent?.[selectedAgent.agentId]; return <div className="agent-inspector-activity"><small>RECENT TASK ACTIVITY</small>{latest ? <><span>{latest.status.toUpperCase()} · {latest.task_id}</span><time dateTime={latest.updated_at}>{new Date(latest.updated_at).toLocaleString()}</time></> : <span>No persisted task activity for this profile yet.</span>}</div> })()}<button type="button" onClick={()=>setSelectedAgent(null)}>CLOSE</button></motion.div>}
    <div className="agent-network-foot"><span>Registered profiles · department-level connectivity · shared core</span><span>Research-only architecture · no broker / order execution</span></div>
  </motion.section>
}
