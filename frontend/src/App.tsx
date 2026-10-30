import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position, addEdge,
  useEdgesState, useNodesState, type Node, type Edge, type Connection
} from '@xyflow/react'
import { Activity, Boxes, BrainCircuit, Cable, ChevronRight, CircleHelp, Database, GitBranch, Play, Search, ShieldCheck, SlidersHorizontal, Workflow, Newspaper } from 'lucide-react'
import PriceChart from './PriceChart'

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
 ['market_input','Market Data Input','data'],['data_quality','Data Quality','validation'],
 ['sma','Simple Moving Average','technical'],['ema','Exponential Moving Average','technical'],
 ['rsi','Relative Strength Index','technical'],['macd','MACD','technical'],
 ['bollinger','Bollinger Bands','technical'],['returns','Returns Analysis','quant'],
 ['volatility','Realized Volatility','quant'],['research_summary','Research Summary','intelligence']
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
 const [researchSymbol,setResearchSymbol] = useState('BTCUSD')
 const [researchIntervals,setResearchIntervals] = useState('15m,1h,4h,1d')
 const [researchCompare,setResearchCompare] = useState('ETHUSD,SOLUSD')
 const [researchReport,setResearchReport] = useState<any>(null)
 const [researchBusy,setResearchBusy] = useState(false)
 const [researchError,setResearchError] = useState('')
 const [researchBars,setResearchBars] = useState<any[]>([])
 const [researchInterval,setResearchInterval] = useState('1h')
 const [selectedCluster,setSelectedCluster] = useState<any>(null)
 const [historyMeta,setHistoryMeta] = useState<any>(null)
 const [researchTimeline,setResearchTimeline] = useState<any[]>([])
 const [timelineBusy,setTimelineBusy] = useState(false)
 const [timelineError,setTimelineError] = useState('')
 const [instrumentQuery,setInstrumentQuery] = useState('')
 const [instrumentResults,setInstrumentResults] = useState<any[]>([])
 const [newsItems,setNewsItems] = useState<any[]>([])
 const [newsBusy,setNewsBusy] = useState(false)
 const [newsError,setNewsError] = useState('')
 const [savedWorkflows,setSavedWorkflows] = useState<any[]>([])
 const [workspaceTitle,setWorkspaceTitle] = useState('My research workspace')
 const [workspaceBusy,setWorkspaceBusy] = useState(false)
 const [sampleBusy,setSampleBusy] = useState(false)
 const [dataLabel,setDataLabel] = useState('MANUAL DEMO INPUT')
 const chartValues = useMemo(()=>values.split(',').map(v=>Number(v.trim())).filter(Number.isFinite),[values])
 useEffect(()=>{fetch(API+'/api/health').then(r=>r.json()).then(()=>setApiState('CONNECTED')).catch(()=>setApiState('OFFLINE'));fetch(API+'/api/workers?limit=550').then(r=>r.json()).then(d=>setWorkers(d.workers||[])).catch(()=>{});refreshWorkspaces()},[])
 const refreshWorkspaces = async()=>{try{const r=await fetch(API+'/api/workspaces');const d=await r.json();setSavedWorkflows(d.workflows||[])}catch{setSavedWorkflows([])}}
 const saveWorkspace = async()=>{setWorkspaceBusy(true);try{const r=await fetch(API+'/api/workspaces',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:workspaceTitle,description:'Saved visual research graph',nodes,edges})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Save failed');await refreshWorkspaces();setResult({status:'saved',workspace:d})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Save failed'})}finally{setWorkspaceBusy(false)}}
 const loadWorkspace = async(id:string)=>{if(!id)return;try{const r=await fetch(API+'/api/workspaces/'+id);const d=await r.json();if(!r.ok)throw new Error(d.detail||'Load failed');setNodes(d.nodes||[]);setEdges(d.edges||[]);setWorkspaceTitle(d.title||'Loaded workspace');setResult({status:'loaded',title:d.title})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Load failed'})}}
 const loadSyntheticSample = async()=>{setSampleBusy(true);try{const r=await fetch(API+'/api/market-data/sample?symbol=BTCUSD&interval=1d&limit=5');const d=await r.json();if(!r.ok)throw new Error(d.detail||'Sample data unavailable');setValues(d.bars.map((b:any)=>String(b.close)).join(','));setDataLabel('SYNTHETIC FIXTURE · NOT MARKET PRICES');setResult({status:'sample_loaded',symbol:d.symbol,interval:d.interval,source:d.source,data_status:d.status,retrieved_at:d.retrieved_at,warnings:d.warnings})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Sample data unavailable'})}finally{setSampleBusy(false)}}
 const findInstruments = async()=>{try{const q=encodeURIComponent(instrumentQuery);const r=await fetch(API+'/api/instruments?q='+q);const d=await r.json();setInstrumentResults(d.instruments||[])}catch{setInstrumentResults([])}}
 const loadNews = async()=>{setNewsBusy(true);setNewsError('');try{const r=await fetch(API+'/api/news');const d=await r.json();setNewsItems((d.items||[]).filter((x:any)=>x.title));const errs=(d.items||[]).filter((x:any)=>x.error);if(errs.length)setNewsError(errs.map((x:any)=>x.source+': '+x.error).join(' · '))}catch(e){setNewsError(e instanceof Error?e.message:'News feed unavailable')}finally{setNewsBusy(false)}}
 const runDeepResearch = async()=> {
  setResearchBusy(true);setResearchError('');setResearchReport(null)
  try {
   const params = new URLSearchParams({symbol:researchSymbol.trim(),intervals:researchIntervals,limit:'500',compare_symbols:researchCompare,breadth_symbols:researchCompare})
   const response = await fetch(API+'/api/research/deep?'+params.toString())
   const body = await response.json()
   if(!response.ok)throw new Error(body.detail||'Deep research unavailable')
   setResearchReport(body)
   const chosen=researchIntervals.split(',').map(x=>x.trim()).includes(researchInterval)?researchInterval:researchIntervals.split(',')[0].trim()
   setResearchInterval(chosen);setSelectedCluster(null)
   const historyResponse=await fetch(API+'/api/market-data/history?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:chosen,limit:'500'}).toString())
   const historyBody=await historyResponse.json()
   if(historyResponse.ok){setResearchBars(historyBody.bars||[]);setHistoryMeta({source:historyBody.source,status:historyBody.status,retrieved_at:historyBody.retrieved_at})}
   else {setResearchBars([]);setHistoryMeta(null)}
   setTimelineBusy(true);setTimelineError('')
   const timelineResponse=await fetch(API+'/api/research/timeline?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:chosen,limit:'200'}).toString())
   const timelineBody=await timelineResponse.json()
   if(timelineResponse.ok)setResearchTimeline(timelineBody.events||[])
   else {setResearchTimeline([]);setTimelineError(timelineBody.detail||'Timeline unavailable')}
   setTimelineBusy(false)
  } catch(e) {setResearchError(e instanceof Error?e.message:'Research API unavailable')}
  finally {setResearchBusy(false)}
 }
 const onConnect = useCallback((connection:Connection)=>setEdges(eds=>addEdge({...connection,animated:true,style:{stroke:'#d39b42',strokeWidth:1.5}},eds)),[setEdges])
 const addNode = (type:string,label:string,category:string) => {
  const id = `node_${Date.now()}`
  const nodeType = type==='market_input'?'market':type==='research_summary'?'output':'worker'
  setNodes(ns=>[...ns,{id,type:nodeType,position:{x:180+Math.random()*500,y:100+Math.random()*450},data:{label,subtitle:`Node · ${type}`,category,period:20,nodeType:type}}])
 }
 const run = async()=> {
  setBusy(true);setResult(null)
  const parsed = values.split(',').map(v=>Number(v.trim())).filter(Number.isFinite)
  const mapped = nodes.map(n=>({...n,type: n.id==='feed'?'market_input':n.id==='quality'?'data_quality':n.id==='trend'?'sma':n.id==='vol'?'volatility':n.id==='report'?'research_summary':(n.data as any).nodeType || ((n.data as NodeData).category==='technical'?'sma':(n.data as NodeData).category==='quant'?'volatility':'research_summary'),data:{period:(n.data as NodeData).period||20}}))
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
  <div className="toolbar"><div className="crumb"><Workflow size={16}/> WORKSPACE <ChevronRight size={14}/> <b>GLOBAL RESEARCH GRAPH</b></div><div className="toolbar-actions"><div className="instrument-search"><input aria-label="Search instruments" placeholder="Find symbol or company…" value={instrumentQuery} onChange={e=>setInstrumentQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')findInstruments()}}/><button className="soft-btn" onClick={findInstruments}><Search size={13}/> FIND</button>{instrumentResults.length>0&&<div className="instrument-results">{instrumentResults.map((item:any)=><div key={item.symbol}><b>{item.symbol}</b><span>{item.name}</span><small>{item.market} · {item.venue} · {item.currency}</small></div>)}</div>}</div><input className="workspace-title" aria-label="Workspace name" value={workspaceTitle} onChange={e=>setWorkspaceTitle(e.target.value)} /><button className="soft-btn" onClick={saveWorkspace} disabled={workspaceBusy}>{workspaceBusy?'SAVING…':'SAVE GRAPH'}</button><select className="workspace-select" aria-label="Load saved workspace" defaultValue="" onChange={e=>loadWorkspace(e.target.value)}><option value="">LOAD WORKSPACE</option>{savedWorkflows.map(w=><option key={w.id} value={w.id}>{w.title}</option>)}</select><button className="soft-btn"><SlidersHorizontal size={14}/> Configure</button><button className="run-btn" onClick={run} disabled={busy}><Play size={14} fill="currentColor"/>{busy?'RUNNING…':'RUN WORKFLOW'}</button></div></div>
  <main className="layout"><aside className="sidebar"><div className="side-tabs"><button className={activeTab==='WORKFLOW'?'active':''} onClick={()=>setActiveTab('WORKFLOW')}><Boxes size={15}/> NODES</button><button className={activeTab==='WORKERS'?'active':''} onClick={()=>setActiveTab('WORKERS')}><BrainCircuit size={15}/> WORKERS</button><button className={activeTab==='NEWS'?'active':''} onClick={()=>setActiveTab('NEWS')}><Newspaper size={15}/> NEWS</button><button className={activeTab==='RESEARCH'?'active':''} onClick={()=>setActiveTab('RESEARCH')}><Activity size={15}/> RESEARCH</button></div>
   {activeTab==='WORKFLOW'&&<><div className="side-label">NODE LIBRARY <span>10</span></div>{palette.map(([id,label,cat])=><button className="palette-item" key={id} onClick={()=>addNode(id,label,cat)}><span className={`palette-icon ${cat}`}>{cat==='data'?<Database size={15}/>:cat==='intelligence'?<BrainCircuit size={15}/>:<GitBranch size={15}/>}</span><span><b>{label}</b><small>{cat.toUpperCase()}</small></span><span className="plus">+</span></button>)}</>}
   {activeTab==='WORKERS'&&<><div className="searchbox"><Search size={14}/><input placeholder="Search 550 workers…" value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="worker-list">{filteredWorkers.map(w=><button className="worker-item" key={w.id} onClick={()=>addNode(w.specialty,w.name,'worker')}><span className="worker-avatar"><BrainCircuit size={13}/></span><span><b>{w.name}</b><small>{w.department.replaceAll('_',' ')}</small></span><span className="plus">+</span></button>)}</div></>}
   {activeTab==='NEWS'&&<div className="news-panel"><button className="run-btn news-refresh" onClick={loadNews} disabled={newsBusy}><Newspaper size={13}/>{newsBusy?'FETCHING…':'FETCH OFFICIAL NEWS'}</button>{newsError&&<p className="news-error">{newsError}</p>}{newsItems.map((item:any)=><a className="news-item" key={item.id} href={item.url} target="_blank" rel="noreferrer"><b>{item.title}</b><small>{item.source} · {item.published_at||'Date unavailable'}</small></a>)}</div>}
   {activeTab==='RESEARCH'&&<div className="research-sidebar">
    <div className="side-label">DEEP RESEARCH <span>DESCRIPTIVE</span></div>
    <label>INSTRUMENT</label><input value={researchSymbol} onChange={e=>setResearchSymbol(e.target.value.toUpperCase())} aria-label="Research symbol"/>
    <label>TIMEFRAMES</label><select value={researchIntervals} onChange={e=>setResearchIntervals(e.target.value)} aria-label="Research timeframes"><option value="15m,1h,4h,1d">15m · 1h · 4h · 1d</option><option value="15m,1h">15m · 1h</option><option value="1h,4h,1d">1h · 4h · 1d</option><option value="1h">1h only</option><option value="4h">4h only</option><option value="1d">1d only</option></select>
    <label>COMPARE / BREADTH SYMBOLS</label><input value={researchCompare} onChange={e=>setResearchCompare(e.target.value)} aria-label="Comparison symbols"/>
    <button className="run-btn research-run" onClick={runDeepResearch} disabled={researchBusy||!researchSymbol.trim()}>{researchBusy?'ANALYZING…':'RUN DEEP RESEARCH'}</button>
    <small className="research-note">Uses locally stored observations only. No live-price claim, forecasts or execution.</small>
    {researchError&&<p className="news-error">{researchError}</p>}
    {researchReport&&<div className="research-results">
      <div className="research-metric"><small>SYMBOL</small><b>{researchReport.symbol}</b></div>
      <div className="research-metric"><small>TIMEFRAMES</small><b>{researchReport.dashboard?.data_quality?.timeframes_checked??0}</b></div>
      <div className="research-metric"><small>QUALITY ISSUES</small><b>{researchReport.dashboard?.data_quality?.timeframes_with_issues??0}</b></div>
      <div className="research-metric"><small>HIGH / LOW CLUSTERS</small><b>{researchReport.dashboard?.historical_price_clusters?.confirmed_swing_high_cluster_count??0} / {researchReport.dashboard?.historical_price_clusters?.confirmed_swing_low_cluster_count??0}</b></div>
      {researchReport.dashboard?.market_breadth_latest&&<div className="research-metric"><small>ADVANCING / DECLINING</small><b>{researchReport.dashboard.market_breadth_latest.advancing} / {researchReport.dashboard.market_breadth_latest.declining}</b></div>}
      <div className="research-frames">{(researchReport.dashboard?.timeframes||[]).map((item:any)=><div key={item.interval}><b>{item.interval}</b><span>{item.status==='available'?item.moving_average_regime:'INSUFFICIENT DATA'}</span><small>RSI {item.rsi14??'—'} · ATR {item.atr14??'—'}</small></div>)}</div>
      <div className="research-cluster-tools">
       <label>CHART TIMEFRAME</label><select value={researchInterval} onChange={async e=>{const interval=e.target.value;setResearchInterval(interval);setSelectedCluster(null);try{const r=await fetch(API+'/api/market-data/history?'+new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'500'}).toString());const d=await r.json();setResearchBars(r.ok?(d.bars||[]):[]);setHistoryMeta(r.ok?{source:d.source,status:d.status,retrieved_at:d.retrieved_at}:null)}catch{setResearchBars([]);setHistoryMeta(null)}}}>{researchIntervals.split(',').map(x=>x.trim()).filter(Boolean).map(x=><option key={x} value={x}>{x}</option>)}</select>
       <small>{researchBars.length} stored bars · {historyMeta?.source||'source unavailable'} · {historyMeta?.status||'status unavailable'}</small>
       {(['historical_swing_high','historical_swing_low'] as const).map(side=><div key={side}><b>{side==='historical_swing_high'?'CONFIRMED HIGH CLUSTERS':'CONFIRMED LOW CLUSTERS'}</b>{(researchReport.timeframes?.[researchInterval]?.historical_price_clusters?.clusters?.[side]||[]).map((cluster:any,index:number)=><button className={selectedCluster===cluster?'cluster-choice selected':'cluster-choice'} key={side+'-'+index} onClick={()=>setSelectedCluster(cluster)}><span>{cluster.mean_price}</span><small>{cluster.touch_count} pivots · {cluster.lower_price}–{cluster.upper_price}</small></button>)}</div>)}
       {selectedCluster&&<div className="cluster-detail"><b>SELECTED HISTORICAL CLUSTER</b><span>Mean: {selectedCluster.mean_price}</span><span>Observed range: {selectedCluster.lower_price} – {selectedCluster.upper_price}</span><span>Confirmed pivots: {selectedCluster.touch_count}</span><span>Pivot times: {selectedCluster.pivot_timestamps.filter(Boolean).join(', ')||'Unavailable'}</span><small>Horizontal chart overlay is a historical reference only, not a forecast or actionable level.</small><button className="soft-btn" onClick={()=>setSelectedCluster(null)}>CLEAR OVERLAY</button></div>}
      </div>
      <div className="research-timeline">
       <div className="timeline-heading"><b>HISTORICAL EVENT TIMELINE</b><small>{timelineBusy?'LOADING…':researchTimeline.length+' OBSERVATIONS'}</small></div>
       {timelineError&&<small className="news-error">{timelineError}</small>}
       {researchTimeline.slice().reverse().slice(0,40).map((event:any)=><div className="timeline-event" key={event.index+'-'+event.timestamp}>
        <time>{event.timestamp||'Timestamp unavailable'}</time>
        <div><b>O {event.open} · H {event.high} · L {event.low} · C {event.close}</b><small>Volume {event.volume} · close change {event.close_change_pct===null?'—':event.close_change_pct+'%'}</small>
        {event.observations?.map((observation:any,index:number)=><small key={index} className="timeline-observation">{observation.type.replaceAll('_',' ')}{observation.labels?' · '+observation.labels.join(', '):''}{observation.price?' · '+observation.price:''}</small>)}
        <small>{event.source} · {event.status} · retrieved {event.retrieved_at||'unknown'}</small></div>
       </div>)}
       <small className="timeline-disclaimer">Historical descriptive observations only. Candle labels and confirmed pivots are not predictive signals.</small>
      </div>
      <button className="soft-btn research-json" onClick={()=>setResult(researchReport)}>OPEN FULL RESEARCH JSON</button>
    </div>}
   </div>}
   <div className="sidebar-bottom"><ShieldCheck size={15}/><span>Governed research environment<small>Data provenance · audit trail</small></span></div>
  </aside>
  <section className="canvas-area"><div className="canvas-meta"><span><span className="live-dot"/> GRAPH EDITOR</span><span>DRAG NODES · CONNECT PORTS · BUILD PIPELINES</span><span>{nodes.length} NODES&nbsp; / &nbsp;{edges.length} LINKS</span></div>
   <div className="canvas"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.2}} defaultEdgeOptions={{animated:true,style:{stroke:'#b18b4d',strokeWidth:1.4}}}><Background color="#30343b" gap={24} size={1}/><MiniMap nodeColor={n=>n.type==='brain'?'#c18d3c':n.type==='market'?'#347f72':'#536b91'} maskColor="rgba(5,8,12,.72)"/><Controls/></ReactFlow></div>
   <PriceChart values={chartValues} bars={researchBars} selectedCluster={selectedCluster} interval={researchInterval} retrievedAt={historyMeta?.retrieved_at||null}/>
   <div className="data-strip"><div><label>INPUT DATA · CLOSE SERIES · {dataLabel}</label><input value={values} onChange={e=>{setValues(e.target.value);setDataLabel("MANUAL DEMO INPUT")}} aria-label="Comma-separated market data values"/></div><button className="soft-btn" onClick={loadSyntheticSample} disabled={sampleBusy}>{sampleBusy?"LOADING…":"LOAD SYNTHETIC SAMPLE"}</button><span>NOT LIVE DATA</span></div>
   {result&&<div className="result-panel"><div className="result-title"><b>EXECUTION INSPECTOR</b><button onClick={()=>setResult(null)}>×</button></div><pre>{JSON.stringify(result,null,2)}</pre></div>}
  </section></main>
  <footer><span><Cable size={14}/> DAG EXECUTION ENGINE</span><span>ALL CALCULATIONS TRACEABLE · HISTORICAL RESEARCH ONLY</span><span>v0.1.0 FOUNDATION</span></footer>
 </div>
}
