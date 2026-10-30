import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position, addEdge,
  useEdgesState, useNodesState, type Node, type Edge, type Connection
} from '@xyflow/react'
import { Activity, BarChart3, Boxes, BrainCircuit, Cable, ChevronRight, CircleHelp, Database, GitBranch, Play, Search, ShieldCheck, SlidersHorizontal, Workflow } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
type NodeData = { label: string; subtitle?: string; category?: string; period?: number; values?: number[]; result?: unknown }
const initialNodes: Node<NodeData>[] = [
 {id:'feed',type:'market',position:{x:40,y:210},data:{label:'Market Data Feed',subtitle:'Input · OHLC / close series',category:'data'}},
 {id:'quality',type:'worker',position:{x:330,y:210},data:{label:'Data Quality Sentinel',subtitle:'Validation · gaps · stale data',category:'validation'}},
 {id:'trend',type:'worker',position:{x:650,y:60},data:{label:'Trend & Momentum',subtitle:'SMA · returns · momentum',category:'technical',period:20}},
 {id:'vol',type:'worker',position:{x:650,y:360},data:{label:'Volatility Analyst',subtitle:'Realized volatility',category:'quant'}},
 {id:'synth',type:'brain',position:{x:980,y:210},data:{label:'Central Intelligence Core',subtitle:'Evidence synthesis · conflicts',category:'intelligence'}},
 {id:'report',type:'output',position:{x:1300,y:210},data:{label:'Research Output',subtitle:'Auditable findings · no execution',category:'output'}}
]
const initialEdges: Edge[] = [
 {id:'e1',source:'feed',target:'quality',animated:true},
 {id:'e2',source:'quality',target:'trend',animated:true},
 {id:'e3',source:'quality',target:'vol',animated:true},
 {id:'e4',source:'trend',target:'synth',animated:true},
 {id:'e5',source:'vol',target:'synth',animated:true},
 {id:'e6',source:'synth',target:'report',animated:true}
]
function TerminalNode({data,selected}: {data:NodeData;selected:boolean}) {
 const cls = data.category || 'worker'
 return <div className={`terminal-node ${cls} ${selected?'selected':''}`}>
  <Handle type="target" position={Position.Left}/>
  <div className="node-head"><span className="node-dot"/><strong>{data.label}</strong><span className="node-menu">•••</span></div>
  <div className="node-body"><span>{data.subtitle || 'Analytical worker'}</span>{data.period && <small>PERIOD <b>{data.period}</b></small>}
   {data.category==='data' && <small>INPUT <b>close[]</b></small>}
   {data.category==='intelligence' && <small>MODE <b>evidence-first</b></small>}
  </div>
  <div className="node-foot"><span>{String(data.category).toUpperCase()}</span><span>READY</span></div>
  <Handle type="source" position={Position.Right}/>
 </div>
}
const nodeTypes = {market:TerminalNode,worker:TerminalNode,brain:TerminalNode,output:TerminalNode}
const palette = [
 ['market_input','Market Input','data'],['data_quality','Data Quality','validation'],['sma','Moving Average','technical'],['returns','Returns Analysis','quant'],['volatility','Realized Volatility','quant'],['research_summary','Research Summary','intelligence']
]
export default function App() {
 const [nodes,setNodes,onNodesChange] = useNodesState<Node<NodeData>>(initialNodes)
 const [edges,setEdges,onEdgesChange] = useEdgesState(initialEdges)
 const [workers,setWorkers] = useState<any[]>([])
 const [search,setSearch] = useState('')
 const [busy,setBusy] = useState(false)
 const [result,setResult] = useState<any>(null)
 const [apiState,setApiState] = useState('CONNECTING')
 const [values,setValues] = useState('100,101,99,103,105,104,108,107,110,112,111,115')
 const [activeTab,setActiveTab] = useState('WORKFLOW')
 useEffect(()=>{fetch(API+'/api/health').then(r=>r.json()).then(()=>setApiState('CONNECTED')).catch(()=>setApiState('OFFLINE'));fetch(API+'/api/workers?limit=550').then(r=>r.json()).then(d=>setWorkers(d.workers||[])).catch(()=>{})},[])
 const onConnect = useCallback((connection:Connection)=>setEdges(eds=>addEdge({...connection,animated:true,style:{stroke:'#d39b42',strokeWidth:1.5}},eds)),[setEdges])
 const addNode = (type:string,label:string,category:string) => {
  const id = `node_${Date.now()}`
  const nodeType = type==='market_input'?'market':type==='research_summary'?'output':'worker'
  setNodes(ns=>[...ns,{id,type:nodeType,position:{x:180+Math.random()*500,y:100+Math.random()*450},data:{label,subtitle:`Node · ${type}`,category,period:20}}])
 }
 const run = async()=> {
  setBusy(true);setResult(null)
  const parsed = values.split(',').map(v=>Number(v.trim())).filter(Number.isFinite)
  const mapped = nodes.map(n=>({...n,type: n.id==='feed'?'market_input':n.id==='quality'?'data_quality':n.id==='trend'?'sma':n.id==='vol'?'volatility':n.id==='report'?'research_summary':(n.data as NodeData).category==='technical'?'sma':(n.data as NodeData).category==='quant'?'volatility':'research_summary',data:{period:(n.data as NodeData).period||20}}))
  try {
   const response=await fetch(API+'/api/workflows/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nodes:mapped,edges:edges.map(e=>({source:e.source,target:e.target})),inputs:{data:parsed}})})
   const body=await response.json();if(!response.ok)throw new Error(body.detail||'Execution failed')
   setResult(body)
  } catch(e){setResult({status:'error',message:e instanceof Error?e.message:'API unavailable'})}
  finally{setBusy(false)}
 }
 const filteredWorkers = useMemo(()=>workers.filter(w=>`${w.name} ${w.department} ${w.specialty}`.toLowerCase().includes(search.toLowerCase())).slice(0,80),[workers,search])
 return <div className="app-shell">
  <header className="topbar"><div className="brand"><div className="brand-mark"><Activity size={19}/></div><div><b>MARKET<span>-MIND</span>-AI</b><small>GLOBAL INTELLIGENCE TERMINAL</small></div></div><div className="top-center"><span className="live-dot"/><span>RESEARCH NETWORK</span><i/> <span>550 WORKER PROFILES</span><i/><span>NO EXECUTION LAYER</span></div><div className="top-right"><span className={apiState==='CONNECTED'?'status-ok':'status-off'}>{apiState}</span><button className="icon-btn"><CircleHelp size={17}/></button></div></header>
  <div className="toolbar"><div className="crumb"><Workflow size={16}/> WORKSPACE <ChevronRight size={14}/> <b>GLOBAL RESEARCH GRAPH</b></div><div className="toolbar-actions"><button className="soft-btn"><SlidersHorizontal size={14}/> Configure</button><button className="run-btn" onClick={run} disabled={busy}><Play size={14} fill="currentColor"/>{busy?'RUNNING…':'RUN WORKFLOW'}</button></div></div>
  <main className="layout"><aside className="sidebar"><div className="side-tabs"><button className={activeTab==='WORKFLOW'?'active':''} onClick={()=>setActiveTab('WORKFLOW')}><Boxes size={15}/> NODES</button><button className={activeTab==='WORKERS'?'active':''} onClick={()=>setActiveTab('WORKERS')}><BrainCircuit size={15}/> WORKERS</button></div>
   {activeTab==='WORKFLOW'?<><div className="side-label">NODE LIBRARY <span>06</span></div>{palette.map(([id,label,cat])=><button className="palette-item" key={id} onClick={()=>addNode(id,label,cat)}><span className={`palette-icon ${cat}`}>{cat==='data'?<Database size={15}/>:cat==='intelligence'?<BrainCircuit size={15}/>:<GitBranch size={15}/>}</span><span><b>{label}</b><small>{cat.toUpperCase()}</small></span><span className="plus">+</span></button>)}</>:<><div className="searchbox"><Search size={14}/><input placeholder="Search 550 workers…" value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="worker-list">{filteredWorkers.map(w=><button className="worker-item" key={w.id} onClick={()=>addNode(w.specialty,w.name,'worker')}><span className="worker-avatar"><BrainCircuit size={13}/></span><span><b>{w.name}</b><small>{w.department.replaceAll('_',' ')}</small></span><span className="plus">+</span></button>)}</div></>}
   <div className="sidebar-bottom"><ShieldCheck size={15}/><span>Governed research environment<small>Data provenance · audit trail</small></span></div>
  </aside>
  <section className="canvas-area"><div className="canvas-meta"><span><span className="live-dot"/> GRAPH EDITOR</span><span>DRAG NODES · CONNECT PORTS · BUILD PIPELINES</span><span>{nodes.length} NODES&nbsp; / &nbsp;{edges.length} LINKS</span></div>
   <div className="canvas"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.2}} defaultEdgeOptions={{animated:true,style:{stroke:'#b18b4d',strokeWidth:1.4}}}><Background color="#30343b" gap={24} size={1}/><MiniMap nodeColor={n=>n.type==='brain'?'#c18d3c':n.type==='market'?'#347f72':'#536b91'} maskColor="rgba(5,8,12,.72)"/><Controls/></ReactFlow></div>
   <div className="data-strip"><div><label>INPUT DATA · CLOSE SERIES</label><input value={values} onChange={e=>setValues(e.target.value)} aria-label="Comma-separated market data values"/></div><span>DEMO DATA · REPLACE WITH CONNECTOR FEED</span></div>
   {result&&<div className="result-panel"><div className="result-title"><b>EXECUTION INSPECTOR</b><button onClick={()=>setResult(null)}>×</button></div><pre>{JSON.stringify(result,null,2)}</pre></div>}
  </section></main>
  <footer><span><Cable size={14}/> DAG EXECUTION ENGINE</span><span>ALL CALCULATIONS TRACEABLE · HISTORICAL RESEARCH ONLY</span><span>v0.1.0 FOUNDATION</span></footer>
 </div>
}
