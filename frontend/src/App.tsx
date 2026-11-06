import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position, addEdge,
  useEdgesState, useNodesState, type Node, type Edge, type Connection
} from '@xyflow/react'
import { Activity, Boxes, BrainCircuit, Cable, ChevronRight, CircleHelp, Database, GitBranch, History, Play, Search, ShieldCheck, SlidersHorizontal, Workflow, Newspaper, Star } from 'lucide-react'
import PriceChart from './PriceChart'
import AgentNetwork from './AgentNetwork'
import AgentPositionMonitor from './AgentPositionMonitor'
import LearningLab from './LearningLab'

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
 const [skills,setSkills] = useState<any[]>([])
 const [selectedSkillIds,setSelectedSkillIds] = useState<string[]>([])
 const [search,setSearch] = useState('')
 const [busy,setBusy] = useState(false)
 const [result,setResult] = useState<any>(null)
 const [apiState,setApiState] = useState('CONNECTING')
 const [validationPayload,setValidationPayload] = useState(JSON.stringify({symbol:'BTCUSD',interval:'1d',status:'historical',source:'manual-review',retrieved_at:new Date().toISOString(),bars:[]},null,2))
 const [validationReport,setValidationReport] = useState<any>(null)
 const [validationBusy,setValidationBusy] = useState(false)
 const [validationError,setValidationError] = useState('')
 const [values,setValues] = useState('100,101,99,103,105,104,108,107,110,112,111,115')
 const [activeTab,setActiveTab] = useState('OVERVIEW')
 const [researchSymbol,setResearchSymbol] = useState('BTCUSD')
 const [researchIntervals,setResearchIntervals] = useState('15m,1h,4h,1d')
 const [researchCompare,setResearchCompare] = useState('ETHUSD,SOLUSD')
 const [researchReport,setResearchReport] = useState<any>(null)
 const [qualityReport,setQualityReport] = useState<any>(null)
 const [benchmarkReport,setBenchmarkReport] = useState<any>(null)
 const [benchmarkBaselineFile,setBenchmarkBaselineFile] = useState<File|null>(null)
 const [benchmarkBusy,setBenchmarkBusy] = useState(false)
 const [benchmarkError,setBenchmarkError] = useState('')
 const [sourceComparison,setSourceComparison] = useState<any>(null)
 const [sourceComparisonBusy,setSourceComparisonBusy] = useState(false)
 const [sourceComparisonError,setSourceComparisonError] = useState('')
 const [qualityBusy,setQualityBusy] = useState(false)
 const [qualityError,setQualityError] = useState('')
 const [researchBusy,setResearchBusy] = useState(false)
 const [researchError,setResearchError] = useState('')
 const [csvText,setCsvText] = useState('timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,100,105,99,103,1200')
 const [csvSource,setCsvSource] = useState('user-historical-csv')
 const [csvBusy,setCsvBusy] = useState(false)
 const [csvMessage,setCsvMessage] = useState('')
 const [csvFileName,setCsvFileName] = useState('')
 const [compareFiles,setCompareFiles] = useState<File[]>([])
 const [exportDiff,setExportDiff] = useState<any>(null)
 const [exportDiffBusy,setExportDiffBusy] = useState(false)
 const [exportDiffError,setExportDiffError] = useState('')
 const [auditLineage,setAuditLineage] = useState<any>(null)
 const [auditBusy,setAuditBusy] = useState(false)
 const [auditError,setAuditError] = useState('')
 const [researchBars,setResearchBars] = useState<any[]>([])
 const [volumeReport,setVolumeReport] = useState<any>(null)
 const [volumeBusy,setVolumeBusy] = useState(false)
 const [volumeError,setVolumeError] = useState('')
 const [liquidityProfile,setLiquidityProfile] = useState<any>(null)
 const [liquidityBusy,setLiquidityBusy] = useState(false)
 const [liquidityError,setLiquidityError] = useState('')
 const [researchInterval,setResearchInterval] = useState('1h')
 const [selectedCluster,setSelectedCluster] = useState<any>(null)
 const [historyMeta,setHistoryMeta] = useState<any>(null)
 const [researchTimeline,setResearchTimeline] = useState<any[]>([])
 const [timelineBusy,setTimelineBusy] = useState(false)
 const [timelineError,setTimelineError] = useState('')
 const [selectedTimelineEvent,setSelectedTimelineEvent] = useState<any>(null)
 const [instrumentQuery,setInstrumentQuery] = useState('')
 const [instrumentResults,setInstrumentResults] = useState<any[]>([])
 const [watchlistItems,setWatchlistItems] = useState<any[]>([])
 const [watchlistBusy,setWatchlistBusy] = useState(false)
 const [watchlistMessage,setWatchlistMessage] = useState('')
 const [marketOverview,setMarketOverview] = useState<any>(null)
 const [overviewBusy,setOverviewBusy] = useState(false)
 const [overviewError,setOverviewError] = useState('')
 const [newsItems,setNewsItems] = useState<any[]>([])
 const [newsBusy,setNewsBusy] = useState(false)
 const [newsError,setNewsError] = useState('')
 const [savedWorkflows,setSavedWorkflows] = useState<any[]>([])
 const [executionRuns,setExecutionRuns] = useState<any[]>([])
 const [selectedRun,setSelectedRun] = useState<any>(null)
 const [runsBusy,setRunsBusy] = useState(false)
 const [replayBusy,setReplayBusy] = useState(false)
 const [runsError,setRunsError] = useState('')
 const [workspaceTitle,setWorkspaceTitle] = useState('My research workspace')
 const [workspaceBusy,setWorkspaceBusy] = useState(false)
 const [sampleBusy,setSampleBusy] = useState(false)
 const [dataLabel,setDataLabel] = useState('MANUAL DEMO INPUT')
 const chartValues = useMemo(()=>values.split(',').map(v=>Number(v.trim())).filter(Number.isFinite),[values])
 useEffect(()=>{fetch(API+'/api/health').then(r=>r.json()).then(()=>setApiState('CONNECTED')).catch(()=>setApiState('OFFLINE'));fetch(API+'/api/workers?limit=550').then(r=>r.json()).then(d=>setWorkers(d.workers||[])).catch(()=>{});fetch(API+'/api/skills').then(r=>r.json()).then(d=>setSkills((d.skills||[]).filter((s:any)=>s.available))).catch(()=>{});refreshWorkspaces();refreshWatchlist();refreshExecutionRuns();loadMarketOverview()},[])

 const runOfflineBenchmark = async()=>{
  setBenchmarkBusy(true);setBenchmarkError('');setBenchmarkReport(null);
  try{
   let baseline:any=undefined
   if(benchmarkBaselineFile){
    if(benchmarkBaselineFile.size>2_000_000)throw new Error('Baseline JSON exceeds 2 MB')
    const parsed=JSON.parse(await benchmarkBaselineFile.text())
    const metrics=parsed.aggregate_metrics||parsed.metrics
    if(!metrics||typeof metrics!=='object')throw new Error('Baseline JSON must contain aggregate_metrics or metrics')
    baseline={metrics:Object.fromEntries(Object.entries(metrics).map(([key,value]:any)=>[key,typeof value==='object'&&value!==null?'mean' in value?value.mean:value:value]))}
   }
   const r=await fetch(API+'/api/research/benchmark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({baseline,regression_threshold:0.05,cases:[
    {case_id:'fixture-valid-reference',draft:'Synthetic fixture; factual meaning is not validated.',claims:[{text:'Synthetic claim A',source_refs:['fixture-source-a']}],source_registry:[{source_id:'fixture-source-a'}]},
    {case_id:'fixture-unknown-reference',draft:'Synthetic fixture with an unknown source reference.',claims:[{text:'Synthetic claim B',source_refs:['unknown-fixture-source']}],source_registry:[{source_id:'fixture-source-a'}]}
   ]})});
   const d=await r.json();if(!r.ok)throw new Error(d.detail||'Offline benchmark failed');setBenchmarkReport(d);
  }catch(e){setBenchmarkError(e instanceof Error?e.message:'Offline benchmark failed')}
  finally{setBenchmarkBusy(false)}
 }
 const refreshWorkspaces = async()=>{try{const r=await fetch(API+'/api/workspaces');const d=await r.json();setSavedWorkflows(d.workflows||[])}catch{setSavedWorkflows([])}}
 const refreshExecutionRuns = async()=>{setRunsBusy(true);setRunsError('');try{const r=await fetch(API+'/api/workflows/runs?limit=50');const d=await r.json();if(!r.ok)throw new Error(d.detail||'Execution history unavailable');setExecutionRuns(d.runs||[])}catch(e){setRunsError(e instanceof Error?e.message:'Execution history unavailable')}finally{setRunsBusy(false)}}
 const inspectExecutionRun = async(id:string)=>{try{const r=await fetch(API+'/api/workflows/runs/'+encodeURIComponent(id));const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not load run');setSelectedRun(d);setResult({...d.result,run_id:d.id,run_record:{id:d.id,status:d.status,parent_run_id:d.parent_run_id}})}catch(e){setRunsError(e instanceof Error?e.message:'Could not load run')}}
 const replayExecutionRun = async(id:string)=>{setReplayBusy(true);setRunsError('');try{const r=await fetch(API+'/api/workflows/runs/'+encodeURIComponent(id)+'/resume',{method:'POST'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Replay failed');setResult(d);setSelectedRun({...d,id:d.run_id,status:d.status||'completed',created_at:new Date().toISOString()});await refreshExecutionRuns()}catch(e){setRunsError(e instanceof Error?e.message:'Replay failed')}finally{setReplayBusy(false)}}
 const loadMarketOverview = async()=>{setOverviewBusy(true);setOverviewError('');try{const r=await fetch(API+'/api/market-data/overview?limit=200');const d=await r.json();if(!r.ok)throw new Error(d.detail||'Stored-data overview unavailable');setMarketOverview(d)}catch(e){setMarketOverview(null);setOverviewError(e instanceof Error?e.message:'Overview unavailable')}finally{setOverviewBusy(false)}}
 const refreshWatchlist = async()=>{try{const r=await fetch(API+'/api/watchlist');const d=await r.json();if(!r.ok)throw new Error('Watchlist unavailable');setWatchlistItems(d.symbols||[])}catch{setWatchlistItems([])}}
 const addToWatchlist = async(symbol:string)=>{setWatchlistBusy(true);setWatchlistMessage('');try{const r=await fetch(API+'/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not save symbol');await refreshWatchlist();setWatchlistMessage(d.already_present?symbol+' ALREADY SAVED':symbol+' ADDED')}catch(e){setWatchlistMessage(e instanceof Error?e.message:'Watchlist update failed')}finally{setWatchlistBusy(false)}}
 const removeFromWatchlist = async(symbol:string)=>{setWatchlistBusy(true);setWatchlistMessage('');try{const r=await fetch(API+'/api/watchlist/'+encodeURIComponent(symbol),{method:'DELETE'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not remove symbol');await refreshWatchlist();setWatchlistMessage(symbol+' REMOVED')}catch(e){setWatchlistMessage(e instanceof Error?e.message:'Watchlist update failed')}finally{setWatchlistBusy(false)}}
 const saveWorkspace = async()=>{setWorkspaceBusy(true);try{const r=await fetch(API+'/api/workspaces',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:workspaceTitle,description:'Saved visual research graph',nodes,edges})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Save failed');await refreshWorkspaces();setResult({status:'saved',workspace:d})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Save failed'})}finally{setWorkspaceBusy(false)}}
 const loadWorkspace = async(id:string)=>{if(!id)return;try{const r=await fetch(API+'/api/workspaces/'+id);const d=await r.json();if(!r.ok)throw new Error(d.detail||'Load failed');setNodes(d.nodes||[]);setEdges(d.edges||[]);setWorkspaceTitle(d.title||'Loaded workspace');setResult({status:'loaded',title:d.title})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Load failed'})}}
 const loadSyntheticSample = async()=>{setSampleBusy(true);try{const r=await fetch(API+'/api/market-data/sample?symbol=BTCUSD&interval=1d&limit=5');const d=await r.json();if(!r.ok)throw new Error(d.detail||'Sample data unavailable');setValues(d.bars.map((b:any)=>String(b.close)).join(','));setDataLabel('SYNTHETIC FIXTURE · NOT MARKET PRICES');setResult({status:'sample_loaded',symbol:d.symbol,interval:d.interval,source:d.source,data_status:d.status,retrieved_at:d.retrieved_at,warnings:d.warnings})}catch(e){setResult({status:'error',message:e instanceof Error?e.message:'Sample data unavailable'})}finally{setSampleBusy(false)}}
 const findInstruments = async()=>{try{const q=encodeURIComponent(instrumentQuery);const r=await fetch(API+'/api/instrument-master?q='+q+'&limit=100');const d=await r.json();if(!r.ok)throw new Error(d.detail||'Instrument search unavailable');setInstrumentResults(d.instruments||[])}catch{setInstrumentResults([])}}
 const loadNews = async()=>{setNewsBusy(true);setNewsError('');try{const r=await fetch(API+'/api/news');const d=await r.json();setNewsItems((d.items||[]).filter((x:any)=>x.title));const errs=(d.items||[]).filter((x:any)=>x.error);if(errs.length)setNewsError(errs.map((x:any)=>x.source+': '+x.error).join(' · '))}catch(e){setNewsError(e instanceof Error?e.message:'News feed unavailable')}finally{setNewsBusy(false)}}
 const loadVolumeIndicators = async()=> {
  if(researchBars.length<2){setVolumeError('At least two stored OHLCV bars are required. Load historical data first.');return}
  setVolumeBusy(true);setVolumeError('')
  try {
   const body={high:researchBars.map((bar:any)=>Number(bar.high)),low:researchBars.map((bar:any)=>Number(bar.low)),close:researchBars.map((bar:any)=>Number(bar.close)),volume:researchBars.map((bar:any)=>Number(bar.volume)),period:20}
   const response=await fetch(API+'/api/indicators/volume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   const data=await response.json()
   if(!response.ok)throw new Error(data.detail||'Volume indicator calculation failed')
   setVolumeReport(data)
  } catch(e){setVolumeReport(null);setVolumeError(e instanceof Error?e.message:'Volume indicator calculation failed')}
  finally{setVolumeBusy(false)}
 }
 const loadLiquidityProfile = async()=> {
  if(researchBars.length<2){setLiquidityError('At least two stored OHLCV bars are required. Load historical data first.');return}
  setLiquidityBusy(true);setLiquidityError('')
  try {
   const body={
    high:researchBars.map((bar:any)=>Number(bar.high)),
    low:researchBars.map((bar:any)=>Number(bar.low)),
    close:researchBars.map((bar:any)=>Number(bar.close)),
    volume:researchBars.map((bar:any)=>Number(bar.volume)),
    bins:48,value_area_pct:70
   }
   const response=await fetch(API+'/api/indicators/liquidity-profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   const data=await response.json()
   if(!response.ok)throw new Error(data.detail||'Liquidity profile calculation failed')
   setLiquidityProfile(data)
  } catch(e){setLiquidityProfile(null);setLiquidityError(e instanceof Error?e.message:'Liquidity profile calculation failed')}
  finally{setLiquidityBusy(false)}
 }
 const loadHistoricalQuality = async(interval:string)=> {
  setQualityBusy(true);setQualityError('')
  try {
   const params=new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'500'})
   const response=await fetch(API+'/api/research/data-quality?'+params.toString())
   const body=await response.json()
   if(!response.ok)throw new Error(body.detail||'Data-quality report unavailable')
   setQualityReport(body)
  } catch(e) {setQualityReport(null);setQualityError(e instanceof Error?e.message:'Data-quality report unavailable')}
  finally {setQualityBusy(false)}
 }
 const loadAuditLineage = async(interval:string)=> {
  setAuditBusy(true);setAuditError('')
  try {
   const params=new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'5000'})
   const [lineageResponse,auditResponse]=await Promise.all([
    fetch(API+'/api/market-data/lineage?'+params.toString()),
    fetch(API+'/api/audit/events?'+new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'20'}).toString())
   ])
   const [lineage,audit]=await Promise.all([lineageResponse.json(),auditResponse.json()])
   if(!lineageResponse.ok)throw new Error(lineage.detail||'Lineage unavailable')
   if(!auditResponse.ok)throw new Error(audit.detail||'Audit history unavailable')
   setAuditLineage({lineage,audit})
  } catch(e) {setAuditLineage(null);setAuditError(e instanceof Error?e.message:'Audit and lineage unavailable')}
  finally {setAuditBusy(false)}
 }
 const loadSourceComparison = async(interval:string)=> {
  setSourceComparisonBusy(true);setSourceComparisonError('')
  try {
   const params=new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'500'})
   const response=await fetch(API+'/api/research/source-comparison?'+params.toString())
   const body=await response.json()
   if(!response.ok)throw new Error(body.detail||'Source comparison unavailable')
   setSourceComparison(body)
  } catch(e) {setSourceComparison(null);setSourceComparisonError(e instanceof Error?e.message:'Source comparison unavailable')}
  finally {setSourceComparisonBusy(false)}
 }
 const compareSavedExports = async()=> {
  if(compareFiles.length!==2){setExportDiffError('SELECT EXACTLY TWO JSON EXPORT FILES');return}
  setExportDiffBusy(true);setExportDiffError('');setExportDiff(null)
  try {
   const [before,after]=await Promise.all(compareFiles.map(async file=>{
    if(file.size>10_000_000)throw new Error(file.name+' exceeds the 10 MB limit')
    return JSON.parse(await file.text())
   }))
   const response=await fetch(API+'/api/research/compare-exports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({before,after})})
   const body=await response.json()
   if(!response.ok)throw new Error(body.detail||'Export comparison failed')
   setExportDiff(body)
  } catch(e) {setExportDiff(null);setExportDiffError(e instanceof Error?e.message:'Could not compare selected exports')}
  finally {setExportDiffBusy(false)}
 }
 const loadCSVFile = async(file?:File)=> {
  if(!file)return
  if(file.size>2_000_000){setCsvMessage('FILE TOO LARGE · MAXIMUM 2 MB');return}
  if(!file.name.toLowerCase().endsWith('.csv')){setCsvMessage('PLEASE SELECT A .CSV FILE');return}
  try {
   const content=await file.text()
   if(!content.trim())throw new Error('Selected CSV file is empty')
   setCsvText(content);setCsvFileName(file.name);setCsvMessage('LOADED '+file.name+' · '+file.size+' BYTES · READY TO IMPORT')
  } catch(e) {setCsvMessage(e instanceof Error?e.message:'Could not read selected file')}
 }
 const importHistoricalCSV = async()=> {
  setCsvBusy(true);setCsvMessage('')
  try {
   const response=await fetch(API+'/api/market-data/import-csv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:csvText,symbol:researchSymbol,interval:researchInterval,source:csvSource})})
   const body=await response.json()
   if(!response.ok)throw new Error(body.detail||'CSV import failed')
   setCsvMessage('IMPORTED '+body.stored+' BARS · '+body.symbol+' · '+body.interval+' · '+body.source)
   const historyResponse=await fetch(API+'/api/market-data/history?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:researchInterval,limit:'500'}).toString())
   const historyBody=await historyResponse.json()
   if(historyResponse.ok){setVolumeReport(null);setVolumeError('');setLiquidityProfile(null);setLiquidityError('');setResearchBars(historyBody.bars||[]);setHistoryMeta({source:historyBody.source,status:historyBody.status,retrieved_at:historyBody.retrieved_at,source_count:historyBody.source_count,timestamp_count:historyBody.timestamp_count,duplicate_timestamp_observations:historyBody.duplicate_timestamp_observations,first_timestamp:historyBody.first_timestamp,last_timestamp:historyBody.last_timestamp,sources:historyBody.sources})}
   const timelineResponse=await fetch(API+'/api/research/timeline?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:researchInterval,limit:'200'}).toString())
   const timelineBody=await timelineResponse.json()
   if(timelineResponse.ok){setResearchTimeline(timelineBody.events||[]);setTimelineError('')}else{setTimelineError(timelineBody.detail||'Timeline refresh unavailable')}
   await loadHistoricalQuality(researchInterval)
   setResult({status:'historical_csv_imported',...body})
  } catch(e) {setCsvMessage(e instanceof Error?e.message:'CSV import failed')}
  finally {setCsvBusy(false)}
 }
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
   await loadHistoricalQuality(chosen)
   const historyResponse=await fetch(API+'/api/market-data/history?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:chosen,limit:'500'}).toString())
   const historyBody=await historyResponse.json()
   if(historyResponse.ok){setVolumeReport(null);setVolumeError('');setResearchBars(historyBody.bars||[]);setHistoryMeta({source:historyBody.source,status:historyBody.status,retrieved_at:historyBody.retrieved_at,source_count:historyBody.source_count,timestamp_count:historyBody.timestamp_count,duplicate_timestamp_observations:historyBody.duplicate_timestamp_observations,first_timestamp:historyBody.first_timestamp,last_timestamp:historyBody.last_timestamp,sources:historyBody.sources})}
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
 const addNode = (type:string,label:string,category:string,skillRefs:string[] = []) => {
  const id = `node_${Date.now()}`
  const nodeType = type==='market_input'?'market':type==='research_summary'?'output':'worker'
  setNodes(ns=>[...ns,{id,type:nodeType,position:{x:180+Math.random()*500,y:100+Math.random()*450},data:{label,subtitle:`Node · ${type}`,category,period:20,nodeType:type,skillRefs}}])
 }
 const run = async()=> {
  setBusy(true);setResult(null)
  const parsed = values.split(',').map(v=>Number(v.trim())).filter(Number.isFinite)
  const mapped = nodes.map(n=>({...n,type: n.id==='feed'?'market_input':n.id==='quality'?'data_quality':n.id==='trend'?'sma':n.id==='vol'?'volatility':n.id==='report'?'research_summary':(n.data as any).nodeType || ((n.data as NodeData).category==='technical'?'sma':(n.data as NodeData).category==='quant'?'volatility':'research_summary'),data:{period:(n.data as NodeData).period||20}}))
  try {
   const response=await fetch(API+'/api/workflows/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nodes:mapped,edges:edges.map(e=>({source:e.source,target:e.target})),inputs:{data:parsed},skill_ids:Array.from(new Set([...selectedSkillIds,...nodes.flatMap(n=>(n.data as any).skillRefs||[])]))})})
   const body=await response.json();if(!response.ok)throw new Error(body.detail||'Execution failed')
   setResult(body)
  } catch(e){setResult({status:'error',message:e instanceof Error?e.message:'API unavailable'})}
  finally{setBusy(false)}
 }
 const filteredWorkers = useMemo(()=>workers.filter(w=>`${w.name} ${w.department} ${w.specialty}`.toLowerCase().includes(search.toLowerCase())).slice(0,80),[workers,search])
 return <div className="app-shell">
  <header className="topbar"><div className="brand"><div className="brand-mark"><Activity size={19}/></div><div><b>MARKET<span>-MIND</span>-AI</b><small>GLOBAL INTELLIGENCE TERMINAL</small></div></div><div className="top-center"><span className="live-dot"/><span>RESEARCH NETWORK</span><i/> <span>550 WORKER PROFILES</span><i/><span>NO EXECUTION LAYER</span></div><div className="top-right"><span className={apiState==='CONNECTED'?'status-ok':'status-off'}>{apiState}</span><a className="soft-btn" href="/market-terminal.html" target="_blank" rel="noreferrer">CLASSIC TERMINAL</a><button className="icon-btn"><CircleHelp size={17}/></button></div></header>
  <div className="toolbar"><div className="crumb"><Workflow size={16}/> WORKSPACE <ChevronRight size={14}/> <b>GLOBAL RESEARCH GRAPH</b></div><div className="toolbar-actions"><div className="instrument-search"><input aria-label="Search instruments" placeholder="Find symbol or company…" value={instrumentQuery} onChange={e=>setInstrumentQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')findInstruments()}}/><button className="soft-btn" onClick={findInstruments}><Search size={13}/> FIND</button>{instrumentResults.length>0&&<div className="instrument-results">{instrumentResults.map((item:any)=><div key={item.symbol}><b>{item.symbol}</b><span>{item.name}</span><small>{item.market} · {item.venue} · {item.currency}</small><button className="soft-btn" onClick={()=>addToWatchlist(item.symbol)} disabled={watchlistBusy}>ADD TO WATCHLIST</button></div>)}</div>}</div><input className="workspace-title" aria-label="Workspace name" value={workspaceTitle} onChange={e=>setWorkspaceTitle(e.target.value)} /><button className="soft-btn" onClick={saveWorkspace} disabled={workspaceBusy}>{workspaceBusy?'SAVING…':'SAVE GRAPH'}</button><select className="workspace-select" aria-label="Load saved workspace" defaultValue="" onChange={e=>loadWorkspace(e.target.value)}><option value="">LOAD WORKSPACE</option>{savedWorkflows.map(w=><option key={w.id} value={w.id}>{w.title}</option>)}</select><button className="soft-btn"><SlidersHorizontal size={14}/> Configure</button><button className="run-btn" onClick={run} disabled={busy}><Play size={14} fill="currentColor"/>{busy?'RUNNING…':'RUN WORKFLOW'}</button></div></div>
  <main className="layout"><aside className="sidebar"><div className="side-tabs"><button className={activeTab==='OVERVIEW'?'active':''} onClick={()=>setActiveTab('OVERVIEW')}><Activity size={15}/> OVERVIEW</button><button className={activeTab==='WORKFLOW'?'active':''} onClick={()=>setActiveTab('WORKFLOW')}><Boxes size={15}/> WORKFLOW</button><button className={activeTab==='AGENT_NETWORK'?'active':''} onClick={()=>setActiveTab('AGENT_NETWORK')}><Cable size={15}/> AGENT NETWORK</button><button className={activeTab==='AGENT_POSITIONS'?'active':''} onClick={()=>setActiveTab('AGENT_POSITIONS')}><Activity size={15}/> AGENT POSITIONS</button><button className={activeTab==='LEARNING'?'active':''} onClick={()=>setActiveTab('LEARNING')}><BrainCircuit size={15}/> LEARNING LAB</button><button className={activeTab==='WORKERS'?'active':''} onClick={()=>setActiveTab('WORKERS')}><BrainCircuit size={15}/> AGENT DIRECTORY</button><button className={activeTab==='RUNS'?'active':''} onClick={()=>{setActiveTab('RUNS');refreshExecutionRuns()}}><History size={15}/> RUNS</button><button className={activeTab==='NEWS'?'active':''} onClick={()=>setActiveTab('NEWS')}><Newspaper size={15}/> NEWS</button><button className={activeTab==='RESEARCH'?'active':''} onClick={()=>setActiveTab('RESEARCH')}><Activity size={15}/> RESEARCH</button><button className={activeTab==='VALIDATION'?'active':''} onClick={()=>setActiveTab('VALIDATION')}><ShieldCheck size={15}/> DATA VALIDATION</button><button className={activeTab==='WATCHLIST'?'active':''} onClick={()=>setActiveTab('WATCHLIST')}><Star size={15}/> WATCHLIST</button></div>
   {activeTab==='WATCHLIST'&&<div className="research-sidebar"><div className="side-label">SAVED INSTRUMENTS <span>{watchlistItems.length}</span></div><button className="soft-btn research-run" onClick={refreshWatchlist} disabled={watchlistBusy}>REFRESH WATCHLIST</button><div className="side-label">LOCAL DATA COVERAGE <span>STORED ONLY</span></div><button className="soft-btn research-run" onClick={loadMarketOverview} disabled={overviewBusy}>{overviewBusy?'LOADING COVERAGE…':'LOAD MARKET DATA OVERVIEW'}</button>{overviewError&&<small className="news-error">{overviewError}</small>}{marketOverview&&<div className="research-results"><b>{marketOverview.instrument_interval_count} SYMBOL / TIMEFRAME SETS</b>{marketOverview.coverage.map((item:any)=><div className="aligned-row" key={item.symbol+'-'+item.interval}><b>{item.symbol}</b><span>{item.interval}</span><span>{item.observation_count} observations</span><small>{item.sources.join(', ')} · {item.statuses.join(', ')} · last {item.last_timestamp||'—'}</small></div>)}<small>{marketOverview.data_note}</small></div>}{watchlistMessage&&<small className="research-note">{watchlistMessage}</small>}{watchlistItems.map(item=><div className="aligned-row" key={item.symbol}><b>{item.symbol}</b><small>Added {item.added_at}</small><button className="soft-btn" onClick={()=>{setResearchSymbol(item.symbol);setActiveTab('RESEARCH')}}>RESEARCH</button><button className="soft-btn" onClick={()=>removeFromWatchlist(item.symbol)} disabled={watchlistBusy}>REMOVE</button></div>)}{watchlistItems.length===0&&<small className="research-note">No saved instruments yet. Search an instrument in the header and choose ADD TO WATCHLIST.</small>}</div>}
   {activeTab==='WORKFLOW'&&<><div className="side-label">NODE LIBRARY <span>10</span></div>{palette.map(([id,label,cat])=><button className="palette-item" key={id} onClick={()=>addNode(id,label,cat)}><span className={`palette-icon ${cat}`}>{cat==='data'?<Database size={15}/>:cat==='intelligence'?<BrainCircuit size={15}/>:<GitBranch size={15}/>}</span><span><b>{label}</b><small>{cat.toUpperCase()}</small></span><span className="plus">+</span></button>)}</>}
   {activeTab==='RUNS'&&<div className="run-history-panel"><div className="side-label">EXECUTION HISTORY <span>{executionRuns.length} RUNS</span></div><button className="soft-btn research-run" onClick={refreshExecutionRuns} disabled={runsBusy}>{runsBusy?'REFRESHING…':'REFRESH HISTORY'}</button>{runsError&&<small className="news-error">{runsError}</small>}{executionRuns.length===0&&!runsBusy&&<small className="research-note">No saved workflow runs yet. Execute a research workflow to create its first record.</small>}{executionRuns.map(item=><div className={selectedRun?.id===item.id?'run-history-item selected':'run-history-item'} key={item.id}><button className="run-history-open" onClick={()=>inspectExecutionRun(item.id)}><b>{item.status.replaceAll('_',' ').toUpperCase()}</b><small>{item.id}</small><small>{item.created_at}</small>{item.parent_run_id&&<small>Replay of {item.parent_run_id}</small>}</button><button className="soft-btn" onClick={()=>replayExecutionRun(item.id)} disabled={replayBusy}>{replayBusy?'RESUMING…':'RESUME CHECKPOINT'}</button></div>)}{selectedRun&&<div className="run-history-detail"><b>SELECTED RUN</b><small>{selectedRun.id}</small><small>{selectedRun.status} · {selectedRun.created_at}</small><small>{selectedRun.result?.aggregation?.completed_count||selectedRun.aggregation?.completed_count||0} completed · {selectedRun.result?.aggregation?.failed_count||selectedRun.aggregation?.failed_count||0} failed · {selectedRun.result?.aggregation?.skipped_count||selectedRun.aggregation?.skipped_count||0} skipped</small>{selectedRun.recovery&&<><small>RECOVERY · {selectedRun.recovery.restored_task_count} tasks restored · {selectedRun.recovery.checkpoint_completed_layers} layers saved</small><small>CHECKPOINT AGE · {selectedRun.recovery.checkpoint_age_seconds===null?'unavailable':selectedRun.recovery.checkpoint_age_seconds.toFixed(3)+' seconds'}</small></>}<button className="soft-btn" onClick={()=>setSelectedRun(null)}>CLOSE DETAILS</button></div>}</div>}
   {activeTab==='WORKERS'&&<><div className="searchbox"><Search size={14}/><input placeholder="Search 550 worker profiles…" value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="skill-picker"><div className="side-label">RESEARCH PLAYBOOKS <span>{selectedSkillIds.length} SELECTED</span></div><small className="skill-note">Choose guidance to load into the next workflow run. Research and paper-only context.</small>{skills.map((skill:any)=><label className="skill-option" key={skill.id}><input type="checkbox" checked={selectedSkillIds.includes(skill.id)} onChange={e=>setSelectedSkillIds(current=>e.target.checked?[...current,skill.id]:current.filter(id=>id!==skill.id))}/><span><b>{skill.id.replace('trader-','').replaceAll('-',' ')}</b><small>{skill.description}</small></span></label>)}</div><div className="worker-list">{filteredWorkers.map(w=><button className="worker-item" key={w.id} onClick={()=>addNode(w.specialty,w.name,'worker',w.skill_refs||[])}><span className="worker-avatar"><BrainCircuit size={13}/></span><span><b>{w.name}</b><small>{w.department.replaceAll('_',' ')} · {(w.skill_refs||[]).join(', ')||'general research'}</small></span><span className="plus">+</span></button>)}</div></>}
   {activeTab==='NEWS'&&<div className="news-panel"><button className="run-btn news-refresh" onClick={loadNews} disabled={newsBusy}><Newspaper size={13}/>{newsBusy?'FETCHING…':'FETCH OFFICIAL NEWS'}</button>{newsError&&<p className="news-error">{newsError}</p>}{newsItems.map((item:any)=><a className="news-item" key={item.id} href={item.url} target="_blank" rel="noreferrer"><b>{item.title}</b><small>{item.source} · {item.published_at||'Date unavailable'}</small></a>)}</div>}
   {activeTab==='RESEARCH'&&<div className="research-sidebar">
    <div className="side-label">HISTORICAL CSV IMPORT <span>LOCAL DATA</span></div>
    <small className="research-note">Paste CSV columns: timestamp,open,high,low,close,volume. Timestamps need an explicit timezone. Max 2 MB / 5,000 rows.</small>
    <label>DATA SOURCE LABEL</label><input value={csvSource} onChange={e=>setCsvSource(e.target.value)} aria-label="CSV source label"/>
    <label>SELECT CSV FILE</label><input type="file" accept=".csv,text/csv" aria-label="Select historical CSV file" onChange={e=>loadCSVFile(e.target.files?.[0])}/>
    {csvFileName&&<small className="research-note">SELECTED FILE: {csvFileName}</small>}
    <label>CSV CONTENT</label><textarea value={csvText} onChange={e=>setCsvText(e.target.value)} aria-label="Historical OHLCV CSV" rows={6}/>
    <button className="soft-btn research-run" onClick={importHistoricalCSV} disabled={csvBusy||!csvText.trim()||!csvSource.trim()}>{csvBusy?'IMPORTING…':'IMPORT HISTORICAL CSV'}</button>
    {csvMessage&&<p className="research-note">{csvMessage}</p>}

    <div className="side-label">OFFLINE RESEARCH BENCHMARK <span>FIXTURE ONLY</span></div>
    <small className="research-note">Run a reproducible structural traceability check on two synthetic cases. No live market data or trading.</small>
    <label>OPTIONAL BASELINE REPORT JSON</label>
    <input type="file" accept=".json,application/json" aria-label="Upload previous benchmark JSON" onChange={e=>setBenchmarkBaselineFile(e.target.files?.[0]||null)}/>
    <small className="research-note">{benchmarkBaselineFile?('Baseline selected: '+benchmarkBaselineFile.name):'Upload a previously downloaded benchmark report to compare structural metrics.'}</small>
    <button className="soft-btn research-run" onClick={runOfflineBenchmark} disabled={benchmarkBusy}>{benchmarkBusy?'RUNNING BENCHMARK…':'RUN OFFLINE BENCHMARK'}</button>
    {benchmarkError&&<small className="news-error">{benchmarkError}</small>}
    {benchmarkReport&&<div className="research-results"><b>BENCHMARK {benchmarkReport.benchmark_id}</b><div className="aligned-row"><span>Cases</span><b>{benchmarkReport.case_count}</b></div>{Object.entries(benchmarkReport.aggregate_metrics||{}).map(([key,value]:any)=><div className="aligned-row" key={key}><span>{key.replaceAll('_',' ').toUpperCase()}</span><b>{value.mean===null?'N/A':(value.mean*100).toFixed(1)+'%'}</b></div>)}
    {benchmarkReport.regression_summary&&<><div className="aligned-row"><span>BASELINE CHECK</span><b>{benchmarkReport.regression_summary.status.replaceAll('_',' ').toUpperCase()}</b></div>{(benchmarkReport.regression_summary.items||[]).map((item:any)=><div className="aligned-row" key={item.metric}><span>{item.metric.replaceAll('_',' ').toUpperCase()}</span><b>{(item.delta*100).toFixed(1)} pp drop</b></div>)}</>}
    <small>Structural traceability only—not factual accuracy, agent intelligence, or trading performance.</small><button className="soft-btn" onClick={()=>{const blob=new Blob([JSON.stringify(benchmarkReport,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='market-mind-offline-benchmark.json';a.click();URL.revokeObjectURL(url)}}>DOWNLOAD BENCHMARK JSON</button></div>}
    <div className="side-label">DEEP RESEARCH <span>DESCRIPTIVE</span></div>
    <label>INSTRUMENT</label><input value={researchSymbol} onChange={e=>setResearchSymbol(e.target.value.toUpperCase())} aria-label="Research symbol"/>
    <label>TIMEFRAMES</label><select value={researchIntervals} onChange={e=>setResearchIntervals(e.target.value)} aria-label="Research timeframes"><option value="15m,1h,4h,1d">15m · 1h · 4h · 1d</option><option value="15m,1h">15m · 1h</option><option value="1h,4h,1d">1h · 4h · 1d</option><option value="1h">1h only</option><option value="4h">4h only</option><option value="1d">1d only</option></select>
    <label>COMPARE / BREADTH SYMBOLS</label><input value={researchCompare} onChange={e=>setResearchCompare(e.target.value)} aria-label="Comparison symbols"/>
    <button className="run-btn research-run" onClick={runDeepResearch} disabled={researchBusy||!researchSymbol.trim()}>{researchBusy?'ANALYZING…':'RUN DEEP RESEARCH'}</button>
    <a className="soft-btn research-run" href={API+'/api/research/export?'+new URLSearchParams({symbol:researchSymbol.trim(),interval:researchInterval,limit:'500'}).toString()} download={researchSymbol.trim().toUpperCase()+'-'+researchInterval+'-research-evidence.json'} aria-label="Download historical research evidence JSON">DOWNLOAD RESEARCH EVIDENCE JSON</a>
    <small className="research-note">Uses locally stored observations only. No live-price claim, forecasts or execution.</small>
    <div className="side-label">DATA AUDIT & LINEAGE <span>PROVENANCE</span></div>
    <button className="soft-btn research-run" onClick={()=>loadAuditLineage(researchInterval)} disabled={auditBusy}>{auditBusy?'LOADING AUDIT…':'VIEW INGESTION AUDIT & LINEAGE'}</button>
    {auditError&&<p className="news-error">{auditError}</p>}
    {auditLineage&&<div className="research-results">
     <b>STORED DATA LINEAGE · {auditLineage.lineage.symbol} · {auditLineage.lineage.interval}</b>
     <small>{auditLineage.lineage.observation_count} observations in selected history window</small>
     {auditLineage.lineage.lineage.map((item:any)=><div className="aligned-row" key={item.source+'-'+item.status}>
      <b>{item.source}</b><span>{item.status}</span><span>{item.observation_count} bars</span>
      <small>{item.first_timestamp||'—'} → {item.last_timestamp||'—'} · retrieved {item.latest_retrieval||'—'}</small>
     </div>)}
     <b>RECENT INGESTION EVENTS · {auditLineage.audit.count}</b>
     {auditLineage.audit.events.slice(0,10).map((event:any)=><small key={event.id}>#{event.id} · {event.event_type} · {event.source} · {event.observation_count} observations · {event.occurred_at}</small>)}
     <small>Audit records describe successful batch writes and source metadata; they do not authenticate a provider or user.</small>
    </div>}
    <div className="side-label">COMPARE SAVED EXPORTS <span>JSON</span></div>
    <small className="research-note">Choose two compatible historical evidence JSON files. Each file is limited to 10 MB.</small>
    <input type="file" accept=".json,application/json" multiple aria-label="Select two historical research JSON exports" onChange={e=>{setCompareFiles(Array.from(e.target.files||[]).slice(0,2));setExportDiff(null);setExportDiffError('')}}/>
    {compareFiles.length>0&&<small className="research-note">SELECTED: {compareFiles.map(file=>file.name).join(' · ')}</small>}
    <button className="soft-btn research-run" onClick={compareSavedExports} disabled={exportDiffBusy||compareFiles.length!==2}>{exportDiffBusy?'COMPARING EXPORTS…':'COMPARE TWO EXPORTS'}</button>
    {exportDiffError&&<p className="news-error">{exportDiffError}</p>}
    {exportDiff&&<div className="research-results">
     <b>EXPORT DIFFERENCE REPORT</b>
     <div className="research-metric"><small>ADDED / REMOVED</small><b>{exportDiff.counts.added} / {exportDiff.counts.removed}</b></div>
     <div className="research-metric"><small>CHANGED / UNCHANGED</small><b>{exportDiff.counts.changed} / {exportDiff.counts.unchanged}</b></div>
     <div className="research-metric"><small>INTEGRITY · BEFORE / AFTER</small><b>{exportDiff.integrity_validation.before.valid?'VALID':exportDiff.integrity_validation.before.reason} / {exportDiff.integrity_validation.after.valid?'VALID':exportDiff.integrity_validation.after.reason}</b></div>
     {exportDiff.provenance_changed_fields.length>0&&<small>PROVENANCE CHANGED: {exportDiff.provenance_changed_fields.join(', ')}</small>}
     {exportDiff.changed.slice(0,10).map((item:any)=><small key={item.timestamp+'-'+item.source}>{item.timestamp} · {item.source} · changed: {item.fields.join(', ')}</small>)}
     <small>Exact timestamp/source matching. A valid digest checks integrity, not provider authenticity.</small>
    </div>}

    <div className="aligned-comparison volume-indicator-panel">
     <div className="timeline-heading"><b>VOLUME INTELLIGENCE</b><button className="soft-btn" onClick={loadVolumeIndicators} disabled={volumeBusy||researchBars.length<2}>{volumeBusy?'CALCULATING…':'CALCULATE FROM LOADED OHLCV'}</button></div>
     <small>Uses {researchBars.length} loaded historical bars · {researchSymbol} · {researchInterval}. Rolling period: 20 bars. No live feed or trade signal.</small>
     {volumeError&&<small className="news-error">{volumeError}</small>}
     {volumeReport&&<div className="volume-indicator-grid">
      {[
       ['OBV','obv','On-Balance Volume'],['ADL','adl','Accumulation / Distribution'],['CMF','cmf','Chaikin Money Flow'],['MFI','mfi','Money Flow Index'],['VWAP','vwap','Volume-weighted average price'],['RELATIVE VOLUME','relative_volume','Volume / rolling average'],['VOLUME OSCILLATOR','volume_oscillator','Fast vs slow volume EMA'],['VOLUME ROC','volume_rate_of_change','Volume rate of change'],['FORCE INDEX','force_index','Price change × volume'],['EASE OF MOVEMENT','ease_of_movement','Price movement relative to volume'],['VPT','vpt','Volume Price Trend'],['CHAIKIN OSC.','chaikin_oscillator','A/D line EMA spread']
      ].map(([label,key,description]:any)=><div className="volume-indicator-cell" key={key}><small>{label}</small><b>{volumeReport[key]?.[volumeReport[key].length-1]===null||volumeReport[key]?.[volumeReport[key].length-1]===undefined?'INSUFFICIENT HISTORY':Number(volumeReport[key][volumeReport[key].length-1]).toLocaleString(undefined,{maximumFractionDigits:4})}</b><span>{description}</span></div>)}
     </div>}
     <small>Historical calculations from the loaded bar sequence. Early readings may be less stable; missing values reflect warm-up or zero-volume conditions.</small>
    </div>
    <div className="aligned-comparison volume-indicator-panel liquidity-profile-panel">
     <div className="timeline-heading"><b>LIQUIDITY PROFILE · HISTORICAL</b><button className="soft-btn" onClick={loadLiquidityProfile} disabled={liquidityBusy||researchBars.length<2}>{liquidityBusy?'CALCULATING…':'CALCULATE PROFILE'}</button></div>
     <small>Approximate volume-at-price using typical candle prices · {researchBars.length} bars · 48 bins · 70% value area.</small>
     {liquidityError&&<small className="news-error">{liquidityError}</small>}
     {liquidityProfile&&<>
      <div className="volume-indicator-grid">
       {[
        ['POINT OF CONTROL','poc'],['VALUE AREA HIGH','value_area_high'],['VALUE AREA LOW','value_area_low'],
        ['TOTAL VOLUME','total_volume'],['VALUE AREA COVERED','value_area_volume_pct_actual']
       ].map(([label,key]:any)=><div className="volume-indicator-cell" key={key}><small>{label}</small><b>{liquidityProfile[key]===null||liquidityProfile[key]===undefined?'—':Number(liquidityProfile[key]).toLocaleString(undefined,{maximumFractionDigits:4})+(key==='value_area_volume_pct_actual'?'%':'')}</b><span>Historical OHLCV calculation</span></div>)}
      </div>
      <div className="liquidity-profile-bars">
       {liquidityProfile.profile.filter((item:any)=>item.volume>0).map((item:any,index:number)=>{
        const max=Math.max(...liquidityProfile.profile.map((row:any)=>row.volume),1)
        return <div className="liquidity-profile-row" key={index}><small>{Number(item.price_mid).toLocaleString(undefined,{maximumFractionDigits:4})}</small><div className="liquidity-profile-track"><i style={{width:(item.volume/max*100)+'%'}}/></div><small>{Number(item.share_pct).toFixed(1)}%</small></div>
       })}
      </div>
      <small>Classification: {liquidityProfile.metadata.classification}. This is an OHLCV approximation, not exchange order-book depth or a trade-level footprint.</small>
     </>}
    </div>
    {researchError&&<p className="news-error">{researchError}</p>}
    {researchReport&&<div className="research-results">
      <div className="research-metric"><small>SYMBOL</small><b>{researchReport.symbol}</b></div>
      <div className="research-metric"><small>TIMEFRAMES</small><b>{researchReport.dashboard?.data_quality?.timeframes_checked??0}</b></div>
      <div className="research-metric"><small>QUALITY ISSUES</small><b>{researchReport.dashboard?.data_quality?.timeframes_with_issues??0}</b></div>
      <div className="research-metric"><small>HIGH / LOW CLUSTERS</small><b>{researchReport.dashboard?.historical_price_clusters?.confirmed_swing_high_cluster_count??0} / {researchReport.dashboard?.historical_price_clusters?.confirmed_swing_low_cluster_count??0}</b></div>
      {researchReport.dashboard?.market_breadth_latest&&<div className="research-metric"><small>ADVANCING / DECLINING</small><b>{researchReport.dashboard.market_breadth_latest.advancing} / {researchReport.dashboard.market_breadth_latest.declining}</b></div>}
      <div className="research-frames">{(researchReport.dashboard?.timeframes||[]).map((item:any)=><div key={item.interval}><b>{item.interval}</b><span>{item.status==='available'?item.moving_average_regime:'INSUFFICIENT DATA'}</span><small>RSI {item.rsi14??'—'} · ATR {item.atr14??'—'}</small></div>)}</div>
      <div className="aligned-comparison">
       <b>HISTORICAL SEASONALITY · {researchInterval}</b>
       {researchReport.timeframes?.[researchInterval]?.seasonality&&<>
        <small>{researchReport.timeframes[researchInterval].seasonality.status.replaceAll('_',' ')} · {researchReport.timeframes[researchInterval].seasonality.return_observations} consecutive-return observations · {researchReport.timeframes[researchInterval].seasonality.skipped_observations} skipped</small>
        <b>BY WEEKDAY</b>
        {researchReport.timeframes[researchInterval].seasonality.by_weekday.map((item:any)=><div className="aligned-row" key={item.bucket}><b>{item.bucket}</b><span>{item.sample_count} samples</span><span>Mean {item.mean_return_pct}%</span><span>Median {item.median_return_pct}%</span></div>)}
        <b>BY CALENDAR MONTH</b>
        {researchReport.timeframes[researchInterval].seasonality.by_calendar_month.map((item:any)=><div className="aligned-row" key={item.bucket}><b>{item.bucket}</b><span>{item.sample_count} samples</span><span>Mean {item.mean_return_pct}%</span><span>Median {item.median_return_pct}%</span></div>)}
        <small>No annualization, significance test, forecast or predictive edge. Consecutive available observations are grouped by the later bar's timestamp.</small>
       </>}
      </div>
      <div className="aligned-comparison">
       <b>HISTORICAL DATA-QUALITY REVIEW · {researchInterval}</b>
       {qualityBusy&&<small>CALCULATING DIAGNOSTICS…</small>}
       {qualityError&&<small className="news-error">{qualityError}</small>}
       {qualityReport&&<>
        <small>{qualityReport.bars_checked} observations reviewed · timestamp spacing: {qualityReport.timestamp_spacing.status.replaceAll('_',' ')}</small>
        <div className="aligned-row"><b>SPACING ANOMALIES</b><span>{qualityReport.timestamp_spacing.spacing_anomaly_count}</span><span>Expected interval {qualityReport.timestamp_spacing.expected_interval_seconds??'—'} sec</span></div>
        <div className="aligned-row"><b>INVALID TIMESTAMPS</b><span>{qualityReport.timestamp_integrity?.invalid_timestamp_count??'—'}</span><span>Timezone-aware values required</span></div>
        <div className="aligned-row"><b>DUPLICATE INSTANTS</b><span>{qualityReport.timestamp_integrity?.duplicate_timestamp_count??'—'}</span><span>Equivalent UTC offsets included</span></div>
        <div className="aligned-row"><b>OUT-OF-ORDER BARS</b><span>{qualityReport.timestamp_integrity?.out_of_order_count??'—'}</span><span>Original sequence retained</span></div>
        {(qualityReport.timestamp_integrity?.invalid_timestamps||[]).slice(0,3).map((item:any)=><small key={'invalid-'+item.bar_index}>Invalid timestamp: bar #{item.bar_index} · {String(item.timestamp)}</small>)}
        {(qualityReport.timestamp_integrity?.duplicate_timestamps||[]).slice(0,3).map((item:any)=><small key={'duplicate-'+item.bar_index}>Duplicate instant: bars #{item.first_bar_index} / #{item.bar_index} · {item.timestamp}</small>)}
        {(qualityReport.timestamp_integrity?.out_of_order_timestamps||[]).slice(0,3).map((item:any)=><small key={'order-'+item.bar_index}>Out of order: bar #{item.bar_index} · {item.timestamp} follows {item.previous_timestamp}</small>)}
        <div className="aligned-row"><b>RETURN OUTLIERS</b><span>{qualityReport.close_to_close_return_outliers.flagged_bar_indices.length}</span><span>{qualityReport.close_to_close_return_outliers.status.replaceAll('_',' ')}</span></div>
        <div className="aligned-row"><b>VOLUME OUTLIERS</b><span>{qualityReport.volume_outliers.flagged_bar_indices.length}</span><span>{qualityReport.volume_outliers.status.replaceAll('_',' ')}</span></div>
        {qualityReport.timestamp_spacing.spacing_anomalies.slice(0,5).map((gap:any)=><small key={gap.from_index+'-'+gap.to_index}>Spacing: {gap.from_timestamp||('bar '+gap.from_index)} → {gap.to_timestamp||('bar '+gap.to_index)} · {gap.elapsed_seconds}s ({gap.interval_multiples} intervals)</small>)}
        {qualityReport.close_to_close_return_outliers.flagged_observations.slice(0,5).map((item:any)=><small key={'return-'+item.bar_index}>Return flag: {item.timestamp} · {item.return_pct}% · close {item.close} (previous {item.previous_close})</small>)}
        {qualityReport.volume_outliers.flagged_observations.slice(0,5).map((item:any)=><small key={'volume-'+item.bar_index}>Volume flag: {item.timestamp} · volume {item.volume}</small>)}
        <small>Outliers are statistical review flags, not proof of bad data. Timestamp gaps do not account for exchange sessions, holidays or provider schedules. No bars or prices are generated.</small>
        <div className="source-comparison">
         <div className="timeline-heading"><b>CROSS-SOURCE COMPARISON</b><button className="soft-btn" onClick={()=>loadSourceComparison(researchInterval)} disabled={sourceComparisonBusy}>{sourceComparisonBusy?'COMPARING…':'COMPARE SOURCES'}</button></div>
         {sourceComparisonError&&<small className="news-error">{sourceComparisonError}</small>}
         {sourceComparison&&<>
          <small>{sourceComparison.source_count} sources · {sourceComparison.shared_timestamp_count} shared UTC timestamps · {sourceComparison.observations_checked} observations checked</small>
          {sourceComparison.comparisons.slice(0,8).map((item:any)=><div className="aligned-row" key={item.timestamp_utc}>
           <b>{item.timestamp_utc}</b><span>{item.source_count} sources</span><span>Close spread {item.field_ranges.close.absolute_spread??'—'}</span><span>Volume spread {item.field_ranges.volume.absolute_spread??'—'}</span>
           {Object.entries(item.sources).map(([name,observations]:[string,any])=><div className="source-observation" key={name}>
            <b>{name}</b>
            {observations.map((o:any)=><small key={o.bar_index}>Bar #{o.bar_index} · {o.timestamp} · {o.status||'status unknown'} · retrieved {o.retrieved_at||'unknown'} · O {o.open??'—'} H {o.high??'—'} L {o.low??'—'} C {o.close??'—'} V {o.volume??'—'}</small>)}
           </div>)}
           <small>Close: {item.field_ranges.close.valid_value_count} valid · {item.field_ranges.close.missing_value_count} missing · {item.field_ranges.close.invalid_value_count} invalid · Volume: {item.field_ranges.volume.valid_value_count} valid · {item.field_ranges.volume.missing_value_count} missing · {item.field_ranges.volume.invalid_value_count} invalid</small>
           {['open','high','low','close','volume'].flatMap((field:string)=>item.field_ranges[field].invalid_values.map((bad:any,index:number)=><small key={field+'-'+bad.bar_index+'-'+index}>Invalid {field} · {bad.source} · bar #{bad.bar_index} · raw value {String(bad.raw_value)}</small>))}
          </div>)}
          <small>Exact UTC instants only. Source observations and retrieval metadata are retained; spreads do not rank providers or select a preferred price.</small>
         </>}
        </div>
       </>}
      </div>
      {researchReport.cross_timeframe?.aligned_indicator_comparison&&<div className="aligned-comparison">
       <b>EXACT-TIMESTAMP INDICATOR COMPARISON</b>
       <small>{researchReport.cross_timeframe.aligned_indicator_comparison.status.replaceAll('_',' ')} · {researchReport.cross_timeframe.aligned_indicator_comparison.common_timestamp_count} shared timestamps</small>
       <small>Latest common timestamp: {researchReport.cross_timeframe.aligned_indicator_comparison.latest_common_timestamp||'Unavailable'}</small>
       {researchReport.cross_timeframe.aligned_indicator_comparison.latest_common_observation&&Object.entries(researchReport.cross_timeframe.aligned_indicator_comparison.latest_common_observation).map(([interval,context]:[string,any])=><div className="aligned-row" key={interval}>
        <b>{interval}</b><span>Close {context.close}</span><span>SMA20 {context.sma20??'—'}</span><span>RSI14 {context.rsi14??'—'}</span><span>MACD {context.macd}</span><span>Signal {context.macd_signal}</span>
       </div>)}
       <small>Exact timestamp matches only; no interpolation or forward-filling. These are historical calculations, not signals.</small>
      </div>}
      <div className="research-cluster-tools">
       <label>CHART TIMEFRAME</label><select value={researchInterval} onChange={async e=>{const interval=e.target.value;setResearchInterval(interval);setSelectedCluster(null);setVolumeReport(null);setVolumeError('');await loadHistoricalQuality(interval);try{const r=await fetch(API+'/api/market-data/history?'+new URLSearchParams({symbol:researchSymbol.trim(),interval,limit:'500'}).toString());const d=await r.json();setVolumeReport(null);setVolumeError('');setResearchBars(r.ok?(d.bars||[]):[]);setHistoryMeta(r.ok?{source:d.source,status:d.status,retrieved_at:d.retrieved_at}:null)}catch{setResearchBars([]);setHistoryMeta(null)}}}>{researchIntervals.split(',').map(x=>x.trim()).filter(Boolean).map(x=><option key={x} value={x}>{x}</option>)}</select>
       <small>{researchBars.length} stored observations · {historyMeta?.source||'source unavailable'} · {historyMeta?.status||'status unavailable'}</small>
       {historyMeta&&<small>Sources {historyMeta.source_count??'—'} · distinct timestamps {historyMeta.timestamp_count??'—'} · overlapping observations {historyMeta.duplicate_timestamp_observations??'—'}</small>}
       {historyMeta&&<small>Range {historyMeta.first_timestamp||'—'} → {historyMeta.last_timestamp||'—'} · retrieved {historyMeta.retrieved_at||'—'}</small>}
       {(['historical_swing_high','historical_swing_low'] as const).map(side=><div key={side}><b>{side==='historical_swing_high'?'CONFIRMED HIGH CLUSTERS':'CONFIRMED LOW CLUSTERS'}</b>{(researchReport.timeframes?.[researchInterval]?.historical_price_clusters?.clusters?.[side]||[]).map((cluster:any,index:number)=><button className={selectedCluster===cluster?'cluster-choice selected':'cluster-choice'} key={side+'-'+index} onClick={()=>setSelectedCluster(cluster)}><span>{cluster.mean_price}</span><small>{cluster.touch_count} pivots · {cluster.lower_price}–{cluster.upper_price}</small></button>)}</div>)}
       {selectedCluster&&<div className="cluster-detail"><b>SELECTED HISTORICAL CLUSTER</b><span>Mean: {selectedCluster.mean_price}</span><span>Observed range: {selectedCluster.lower_price} – {selectedCluster.upper_price}</span><span>Confirmed pivots: {selectedCluster.touch_count}</span><span>Pivot times: {selectedCluster.pivot_timestamps.filter(Boolean).join(', ')||'Unavailable'}</span><small>Horizontal chart overlay is a historical reference only, not a forecast or actionable level.</small><button className="soft-btn" onClick={()=>setSelectedCluster(null)}>CLEAR OVERLAY</button></div>}
      </div>
      <div className="research-timeline">
       <div className="timeline-heading"><b>HISTORICAL EVENT TIMELINE</b><small>{timelineBusy?'LOADING…':researchTimeline.length+' OBSERVATIONS'}</small></div>
       {timelineError&&<small className="news-error">{timelineError}</small>}
       {researchTimeline.slice().reverse().slice(0,40).map((event:any)=><button type="button" className={selectedTimelineEvent?.index===event.index?'timeline-event selected':'timeline-event'} key={event.index+'-'+event.timestamp} onClick={()=>setSelectedTimelineEvent(event)}>
        <time>{event.timestamp||'Timestamp unavailable'}</time>
        <div><b>O {event.open} · H {event.high} · L {event.low} · C {event.close}</b><small>Volume {event.volume} · close change {event.close_change_pct===null?'—':event.close_change_pct+'%'}</small>
        {event.observations?.map((observation:any,index:number)=><small key={index} className="timeline-observation">{observation.type.replaceAll('_',' ')}{observation.labels?' · '+observation.labels.join(', '):''}{observation.price?' · '+observation.price:''}</small>)}
        <small>{event.source} · {event.status} · retrieved {event.retrieved_at||'unknown'}</small></div>
       </button>)}
       {selectedTimelineEvent&&<div className="timeline-inspector">
        <div className="timeline-heading"><b>SELECTED OBSERVATION</b><button className="soft-btn" onClick={()=>setSelectedTimelineEvent(null)}>CLEAR</button></div>
        <span>{selectedTimelineEvent.timestamp||'Timestamp unavailable'} · BAR #{selectedTimelineEvent.index}</span>
        <div className="timeline-values"><span>OPEN <b>{selectedTimelineEvent.open}</b></span><span>HIGH <b>{selectedTimelineEvent.high}</b></span><span>LOW <b>{selectedTimelineEvent.low}</b></span><span>CLOSE <b>{selectedTimelineEvent.close}</b></span><span>VOLUME <b>{selectedTimelineEvent.volume}</b></span><span>CHANGE <b>{selectedTimelineEvent.close_change_pct===null?'—':selectedTimelineEvent.close_change_pct+'%'}</b></span></div>
        <small>Source: {selectedTimelineEvent.source} · Status: {selectedTimelineEvent.status}</small>
        <small>Retrieved: {selectedTimelineEvent.retrieved_at||'timestamp unavailable'}</small>
        <small>Observation labels: {selectedTimelineEvent.observations?.length?selectedTimelineEvent.observations.map((x:any)=>x.type.replaceAll('_',' ')).join(', '):'None recorded for this bar'}</small>
        <div className="timeline-indicators"><b>HISTORICAL INDICATOR CONTEXT</b>
         {(['sma20','rsi14','macd','macd_signal','macd_histogram'] as const).map(key=><span key={key}>{key.replace(/_/g,' ').toUpperCase()} <strong>{selectedTimelineEvent.indicator_context?.[key]===null||selectedTimelineEvent.indicator_context?.[key]===undefined?'INSUFFICIENT HISTORY':selectedTimelineEvent.indicator_context[key]}</strong></span>)}
        </div>
        <small>Indicator values describe calculations at this historical bar. Missing values reflect warm-up requirements, not zero readings.</small>
        <small>Historical inspection only. This selection does not produce a forecast or trade instruction.</small>
       </div>}
       <small className="timeline-disclaimer">Historical descriptive observations only. Candle labels and confirmed pivots are not predictive signals.</small>
      </div>
      <button className="soft-btn research-json" onClick={()=>setResult(researchReport)}>OPEN FULL RESEARCH JSON</button>
    </div>}
   </div>}
   <div className="sidebar-bottom"><ShieldCheck size={15}/><span>Governed research environment<small>Data provenance · audit trail</small></span></div>
  </aside>
  {activeTab==='VALIDATION'?<section className="overview-area">
    <div className="overview-heading"><div><span className="eyebrow">MARKET-MIND-AI / DATA QUALITY</span><h1>Market data validation</h1><p>Check an OHLCV payload against the backend data contract before research analysis.</p></div></div>
    <div className="overview-panel validation-panel">
      <label>PAYLOAD JSON</label>
      <textarea className="validation-input" value={validationPayload} onChange={e=>setValidationPayload(e.target.value)} spellCheck={false}/>
      <div className="validation-actions"><button className="run-btn" disabled={validationBusy} onClick={async()=>{setValidationBusy(true);setValidationError('');setValidationReport(null);try{const payload=JSON.parse(validationPayload);const response=await fetch(API+'/api/market-data/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({payload})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Validation request failed');setValidationReport(data)}catch(e){setValidationError(e instanceof Error?e.message:'Validation failed')}finally{setValidationBusy(false)}}}>{validationBusy?'VALIDATING…':'VALIDATE PAYLOAD'}</button><button className="soft-btn" onClick={()=>{setValidationPayload(JSON.stringify({symbol:'BTCUSD',interval:'1d',status:'historical',source:'manual-review',retrieved_at:new Date().toISOString(),bars:[{timestamp:new Date(Date.now()-86400000).toISOString(),open:100,high:105,low:98,close:102,volume:1200}]},null,2));setValidationReport(null);setValidationError('')}}>LOAD SAMPLE</button></div>
      {validationError&&<p className="news-error">{validationError}</p>}
      {validationReport&&<div className="research-results"><div className="overview-status"><span className={validationReport.valid?'status-ok':'status-off'}>{validationReport.result?.toUpperCase()}</span><span>{validationReport.error_count} ERRORS</span><span>{validationReport.bar_count??'—'} BARS</span></div>{Array.isArray(validationReport.errors)&&validationReport.errors.length>0&&<div className="validation-details"><strong>ERROR DETAILS</strong><ul>{validationReport.errors.map((item:any,index:number)=><li key={index}><code>{Array.isArray(item.location)?item.location.join(' → '):item.location||'payload'}</code>: {item.message||item.type||'Invalid value'}</li>)}</ul></div>}{Array.isArray(validationReport.warnings)&&validationReport.warnings.length>0&&<div className="validation-details"><strong>WARNINGS</strong><ul>{validationReport.warnings.map((item:any,index:number)=><li key={index}>{typeof item==='string'?item:item.message||JSON.stringify(item)}</li>)}</ul></div>}<details><summary>RAW VALIDATION REPORT</summary><pre>{JSON.stringify(validationReport,null,2)}</pre></details></div>}
      <small>Structural validation only. It does not verify source authenticity, licensing, freshness or market-session completeness.</small>
    </div>
   </section>:activeTab==='OVERVIEW'?<section className="overview-area">
    <div className="overview-heading"><div><span className="eyebrow">MARKET-MIND-AI / RESEARCH WORKSPACE</span><h1>Market research overview</h1><p>One place to inspect stored market data, research coverage and system readiness.</p></div><button className="soft-btn" onClick={loadMarketOverview} disabled={overviewBusy}>{overviewBusy?'REFRESHING…':'REFRESH OVERVIEW'}</button></div>
    <div className="overview-status"><span className={apiState==='CONNECTED'?'status-ok':'status-off'}>{apiState}</span><span>API CONNECTION</span><span className="overview-separator">·</span><span>{marketOverview?.instrument_interval_count??'—'} SYMBOL / TIMEFRAME SETS</span><span className="overview-separator">·</span><span>{watchlistItems.length} WATCHLIST INSTRUMENTS</span><span className="overview-separator">·</span><span>{workers.length} WORKER TEMPLATES</span></div>
    {overviewError&&<p className="news-error">{overviewError}</p>}
    <div className="overview-grid">
     <article className="overview-card"><span>DATA COVERAGE</span><strong>{marketOverview?.instrument_interval_count??'—'}</strong><small>Stored symbol and timeframe combinations</small></article>
     <article className="overview-card"><span>WATCHLIST</span><strong>{watchlistItems.length}</strong><small>Saved instrument references</small></article>
     <article className="overview-card"><span>RESEARCH WORKERS</span><strong>{workers.length||550}</strong><small>Templates, not active autonomous agents</small></article>
     <article className="overview-card"><span>EXECUTION MODE</span><strong>DISABLED</strong><small>Broker connections and order execution are not configured</small></article>
     <article className="overview-card"><span>STORED OBSERVATIONS</span><strong>{marketOverview?.coverage?.reduce((sum:number,item:any)=>sum+(item.observation_count||0),0)??'—'}</strong><small>Total locally stored OHLCV rows in this overview</small></article>
     <article className="overview-card"><span>RECORDED SOURCES</span><strong>{marketOverview?.coverage?new Set(marketOverview.coverage.flatMap((item:any)=>item.sources||[])).size:'—'}</strong><small>Distinct source labels across stored coverage</small></article>
    </div>
    <div className="overview-columns">
     <section className="overview-panel"><div className="overview-panel-head"><div><b>STORED MARKET DATA</b><small>Local historical observations only</small></div><button className="soft-btn" onClick={()=>setActiveTab('WATCHLIST')}>OPEN WATCHLIST</button></div>
      {marketOverview?.coverage?.length?marketOverview.coverage.map((item:any)=><div className="coverage-row" key={item.symbol+'-'+item.interval}><div><b>{item.symbol}</b><small>{item.interval} · {item.sources?.join(', ')||'source unavailable'}</small></div><span>{item.observation_count} bars</span><small>{item.statuses?.join(', ')||'status unavailable'} · latest {item.last_timestamp||'—'}</small><button className="soft-btn" onClick={()=>{setResearchSymbol(item.symbol);setResearchInterval(item.interval);setActiveTab('RESEARCH')}}>ANALYZE</button></div>):<div className="overview-empty">No stored market history found. Import a historical OHLCV CSV in Research to populate this workspace. Synthetic fixtures are clearly labelled and are not market prices.</div>}
     </section>
     <section className="overview-panel"><div className="overview-panel-head"><div><b>RESEARCH MODULES</b><small>Choose a workspace to inspect details</small></div></div>
      <button className="module-link" onClick={()=>setActiveTab('RESEARCH')}><span><b>Historical research</b><small>CSV import, deep analysis, data quality, source lineage</small></span><ChevronRight size={16}/></button>
      <button className="module-link" onClick={()=>setActiveTab('NEWS')}><span><b>News intelligence</b><small>Source-linked headlines and publication timestamps</small></span><ChevronRight size={16}/></button>
      <button className="module-link" onClick={()=>setActiveTab('WORKERS')}><span><b>Worker directory</b><small>550 specialist templates and relevant research playbooks</small></span><ChevronRight size={16}/></button>
      <button className="module-link" onClick={()=>setActiveTab('RUNS')}><span><b>Workflow history</b><small>Previous runs, task status and checkpoint recovery</small></span><ChevronRight size={16}/></button>
      <button className="module-link" onClick={()=>setActiveTab('WORKFLOW')}><span><b>Visual workflow builder</b><small>Build and inspect research pipelines</small></span><ChevronRight size={16}/></button>
     </section>
    </div>
    <div className="overview-disclaimer">DATA STATUS: {marketOverview?.data_note||'No live market-data provider is configured. Displayed coverage reflects locally stored observations only.'}</div>
   </section>:activeTab==='AGENT_NETWORK'?<AgentNetwork agents={workers}/>:activeTab==='AGENT_POSITIONS'?<AgentPositionMonitor agents={workers}/>:activeTab==='LEARNING'?<LearningLab api={API} agents={workers}/>:<section className="canvas-area"><div className="canvas-meta"><span><span className="live-dot"/> GRAPH EDITOR</span><span>DRAG NODES · CONNECT PORTS · BUILD PIPELINES</span><span>{nodes.length} NODES&nbsp; / &nbsp;{edges.length} LINKS</span></div>
   <div className="canvas"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.2}} defaultEdgeOptions={{animated:true,style:{stroke:'#b18b4d',strokeWidth:1.4}}}><Background color="#30343b" gap={24} size={1}/><MiniMap nodeColor={n=>n.type==='brain'?'#c18d3c':n.type==='market'?'#347f72':'#536b91'} maskColor="rgba(5,8,12,.72)"/><Controls/></ReactFlow></div>
   <PriceChart values={chartValues} bars={researchBars} selectedCluster={selectedCluster} selectedTimestamp={selectedTimelineEvent?.timestamp||null} interval={researchInterval} retrievedAt={historyMeta?.retrieved_at||null}/>
   <div className="data-strip"><div><label>INPUT DATA · CLOSE SERIES · {dataLabel}</label><input value={values} onChange={e=>{setValues(e.target.value);setDataLabel("MANUAL DEMO INPUT")}} aria-label="Comma-separated market data values"/></div><button className="soft-btn" onClick={loadSyntheticSample} disabled={sampleBusy}>{sampleBusy?"LOADING…":"LOAD SYNTHETIC SAMPLE"}</button><span>NOT LIVE DATA</span></div>
   {result&&<div className="result-panel"><div className="result-title"><b>EXECUTION INSPECTOR</b><button onClick={()=>setResult(null)}>×</button></div>{result.skill_context?.length>0&&<div className="execution-skills"><b>LOADED RESEARCH PLAYBOOKS</b><div>{result.skill_context.map((skill:any)=><span key={skill.id}>{skill.id}</span>)}</div><small>{result.skill_context_mode} · broker execution disabled</small></div>}{result.aggregation&&<div className="orchestration-summary"><b>ORCHESTRATION SUMMARY</b><div className="orchestration-stats"><span>{result.aggregation.completed_count}/{result.aggregation.task_count} completed</span><span>{result.aggregation.failed_count||0} failed</span><span>{result.aggregation.skipped_count||0} skipped</span><span>{result.aggregation.result_count} results</span><span>{(result.performance?.total_execution_ns/1000000).toFixed(3)} ms total</span></div>{result.tasks?.map((task:any)=><div className="orchestration-task" key={task.task_id}><span><b>{task.assigned_worker}</b><small>{task.node_type} · depends on {task.dependency_ids.length?task.dependency_ids.join(", "):"none"}</small></span><span><i className={task.status==="failed"?"task-failed":task.status==="skipped"?"task-skipped":""}>{task.status} · {task.attempts||0} attempts</i><small>run {(task.duration_ns/1000).toFixed(1)} µs · wait {(task.queue_wait_ns/1000).toFixed(1)} µs</small>{task.error&&<small className="task-error">{task.error_type}: {task.error}</small>}</span></div>)}</div>}<pre>{JSON.stringify(result,null,2)}</pre></div>}
  </section>}</main>
  <footer><span><Cable size={14}/> DAG EXECUTION ENGINE</span><span>ALL CALCULATIONS TRACEABLE · HISTORICAL RESEARCH ONLY</span><span>v0.1.0 FOUNDATION</span></footer>
 </div>
}
