import { useMemo } from 'react'
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, type Node, type Edge } from '@xyflow/react'
import { Network, BrainCircuit } from 'lucide-react'

type AgentProfile = {
  id?: string
  name?: string
  department?: string
  specialty?: string
  kind?: string
  status?: string
  memory_namespace?: string
}

type AgentNodeData = { label: string; department: string; specialty: string; status: string; core?: boolean }

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
  const { nodes, edges } = useMemo(() => {
    const profiles = agents.slice(0, 550)
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
          status: profile.status || 'PROFILE'
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
  }, [agents])

  return <section className="agent-network-view">
    <div className="agent-network-heading">
      <div><span className="eyebrow">MARKET-MIND-AI / AGENT TOPOLOGY</span><h1><Network size={21}/> 550+ Analytical Agent Network</h1><p>Node-based visual map inspired by the reference image. Each card represents a registered specialist profile; the graph is a topology visualization, not proof that every agent is currently running.</p></div>
      <div className="agent-network-stats"><b>{agents.length || 550}</b><span>REGISTERED PROFILES</span><b>{edges.length.toLocaleString()}</b><span>VISUAL CONNECTIONS</span></div>
    </div>
    <div className="agent-network-legend"><span><i className="core-dot"/> Shared intelligence core</span><span><i className="dept-dot"/> Department links</span><span><i className="agent-dot"/> Agent profile → core</span><span><BrainCircuit size={13}/> Shared model architecture · no paper trading</span></div>
    <div className="agent-network-canvas">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.12, minZoom: 0.04, maxZoom: 1.1 }} minZoom={0.025} maxZoom={2} defaultEdgeOptions={{ animated: false }} nodesDraggable={false}>
        <Background color="#262b32" gap={22} size={1}/>
        <MiniMap nodeColor={n => n.id === 'intelligence-core' ? '#d4a34c' : '#607c98'} maskColor="rgba(5,8,12,.76)"/>
        <Controls/>
      </ReactFlow>
    </div>
    <div className="agent-network-foot"><span>550 profiles · department-level connectivity · shared core</span><span>Research-only architecture · no broker / order execution</span></div>
  </section>
}
