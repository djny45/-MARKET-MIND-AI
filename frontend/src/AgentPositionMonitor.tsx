import { useMemo, useState } from 'react'
import { Activity, BrainCircuit, Search, ShieldAlert, TrendingDown, TrendingUp, Minus, RotateCcw } from 'lucide-react'

type AgentProfile = {
  id?: string
  name?: string
  department?: string
  specialty?: string
  kind?: string
  status?: string
}
type Bias = 'LONG' | 'SHORT' | 'NEUTRAL' | 'UNASSIGNED'
type Props = { agents: AgentProfile[] }

const biasOptions: Bias[] = ['LONG', 'SHORT', 'NEUTRAL', 'UNASSIGNED']
const normalizeId = (agent: AgentProfile, index: number) => String(agent.id || `agent-${index + 1}`)

export default function AgentPositionMonitor({ agents }: Props) {
  const [symbol, setSymbol] = useState('BTCUSD')
  const [query, setQuery] = useState('')
  const [department, setDepartment] = useState('ALL DEPARTMENTS')
  const [biasFilter, setBiasFilter] = useState('ALL BIASES')
  const [biasByAgent, setBiasByAgent] = useState<Record<string, Bias>>({})
  const [selectedId, setSelectedId] = useState('')
  const [visibleCount, setVisibleCount] = useState(50)

  const departments = useMemo(() => ['ALL DEPARTMENTS', ...Array.from(new Set(agents.map(a => a.department || 'General Research'))).sort(), [agents])
  const filtered = useMemo(() => agents.slice(0, 550).filter((agent, index) => {
    const id = normalizeId(agent, index)
    const text = [id, agent.name, agent.department, agent.specialty, agent.kind].join(' ').toLowerCase()
    const bias = biasByAgent[id] || 'UNASSIGNED'
    return text.includes(query.toLowerCase()) &&
      (department === 'ALL DEPARTMENTS' || (agent.department || 'General Research') === department) &&
      (biasFilter === 'ALL BIASES' || bias === biasFilter)
  }), [agents, query, department, biasFilter, biasByAgent])

  const counts = useMemo(() => {
    const result: Record<Bias, number> = { LONG: 0, SHORT: 0, NEUTRAL: 0, UNASSIGNED: 0 }
    agents.slice(0, 550).forEach((agent, index) => { result[biasByAgent[normalizeId(agent, index)] || 'UNASSIGNED']++ })
    return result
  }, [agents, biasByAgent])

  const selected = agents.find((agent, index) => normalizeId(agent, index) === selectedId)
  const setBias = (id: string, bias: Bias) => setBiasByAgent(current => ({ ...current, [id]: bias }))
  const reset = () => { setBiasByAgent({}); setBiasFilter('ALL BIASES'); setQuery(''); setDepartment('ALL DEPARTMENTS'); setSelectedId('') }
  const assignAll = (bias: Bias) => {
    setBiasByAgent(current => {
      const next = { ...current }
      filtered.forEach(agent => {
        const index = agents.indexOf(agent)
        next[normalizeId(agent, index)] = bias
      })
      return next
    })
  }

  return <section className="agent-position-view">
    <header className="agent-position-heading">
      <div><span className="eyebrow">MARKET-MIND-AI / AGENT RESEARCH POSITIONS</span><h1><Activity size={21}/> AI Agent Position Monitor</h1><p>Inspect each registered specialist and manually tag its research stance for the selected instrument. These are analyst labels—not brokerage positions, model-generated signals, or trade instructions.</p></div>
      <div className="agent-position-controls"><label>INSTRUMENT<select value={symbol} onChange={e=>setSymbol(e.target.value)}><option>BTCUSD</option><option>ETHUSD</option><option>SOLUSD</option><option>NIFTY</option><option>SENSEX</option><option>XAUUSD</option><option>USDINR</option></select></label><span className="session-tag">LOCAL SESSION · NOT SAVED</span></div>
    </header>

    <div className="agent-position-warning"><ShieldAlert size={15}/> Research stance board only. No real holdings, long/short exposure, PnL, live market signals, or order execution are connected to this screen.</div>

    <div className="agent-position-summary">
      <button className={biasFilter==='LONG'?'selected long':'long'} onClick={()=>setBiasFilter(biasFilter==='LONG'?'ALL BIASES':'LONG')}><TrendingUp size={17}/><span><b>{counts.LONG}</b><small>LONG / BULLISH</small></span></button>
      <button className={biasFilter==='SHORT'?'selected short':'short'} onClick={()=>setBiasFilter(biasFilter==='SHORT'?'ALL BIASES':'SHORT')}><TrendingDown size={17}/><span><b>{counts.SHORT}</b><small>SHORT / BEARISH</small></span></button>
      <button className={biasFilter==='NEUTRAL'?'selected neutral':'neutral'} onClick={()=>setBiasFilter(biasFilter==='NEUTRAL'?'ALL BIASES':'NEUTRAL')}><Minus size={17}/><span><b>{counts.NEUTRAL}</b><small>NEUTRAL</small></span></button>
      <button className={biasFilter==='UNASSIGNED'?'selected unassigned':'unassigned'} onClick={()=>setBiasFilter(biasFilter==='UNASSIGNED'?'ALL BIASES':'UNASSIGNED')}><BrainCircuit size={17}/><span><b>{counts.UNASSIGNED}</b><small>UNASSIGNED</small></span></button>
    </div>

    <div className="agent-position-toolbar">
      <label className="agent-position-search"><Search size={14}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search agent ID, name, specialty…" /></label>
      <select value={department} onChange={e=>setDepartment(e.target.value)}>{departments.map(d=><option key={d}>{d}</option>)}</select>
      <select value={biasFilter} onChange={e=>setBiasFilter(e.target.value)}>{['ALL BIASES',...biasOptions].map(b=><option key={b}>{b}</option>)}</select>
      <button onClick={()=>assignAll('NEUTRAL')} title="Assign neutral research label to currently filtered agents">TAG FILTERED NEUTRAL</button>
      <button onClick={reset}><RotateCcw size={13}/> RESET</button>
      <span>{filtered.length} matching profiles</span>
    </div>

    <div className="agent-position-table-wrap">
      <table className="agent-position-table">
        <thead><tr><th>AGENT</th><th>DEPARTMENT / SPECIALTY</th><th>PROFILE STATUS</th><th>RESEARCH STANCE · {symbol}</th><th>SET STANCE</th></tr></thead>
        <tbody>{filtered.slice(0, visibleCount).map((agent) => {
          const index = agents.indexOf(agent)
          const id = normalizeId(agent, index)
          const bias = biasByAgent[id] || 'UNASSIGNED'
          return <tr key={id} className={selectedId===id?'active':''} onClick={()=>setSelectedId(id)}>
            <td><b>{agent.name || id}</b><small>{id}</small></td>
            <td><span>{agent.department || 'General Research'}</span><small>{agent.specialty || agent.kind || 'Specialist profile'}</small></td>
            <td><span className="agent-profile-status"><i/> {String(agent.status || 'REGISTERED').toUpperCase()}</span></td>
            <td><span className={`stance-badge ${bias.toLowerCase()}`}>{bias==='UNASSIGNED'?'— NOT TAGGED':bias}</span></td>
            <td><div className="stance-actions">{biasOptions.map(option=><button key={option} className={bias===option?'active '+option.toLowerCase():option.toLowerCase()} onClick={event=>{event.stopPropagation();setBias(id,option)}}>{option==='UNASSIGNED'?'CLEAR':option}</button>)}</div></td>
          </tr>
        })}</tbody>
      </table>
      {filtered.length===0&&<div className="agent-position-empty">No agent profiles match these filters.</div>}
      {filtered.length>visibleCount&&<button className="agent-position-load" onClick={()=>setVisibleCount(n=>Math.min(n+50,550))}>LOAD NEXT 50 PROFILES · {Math.min(filtered.length-visibleCount,50)} MORE</button>}
    </div>

    {selected&&<aside className="agent-position-inspector"><div><span className="eyebrow">SELECTED AGENT</span><h2>{selected.name || selectedId}</h2><small>{selectedId} · {selected.department || 'General Research'}</small></div><div><b>{selected.specialty || selected.kind || 'Specialist profile'}</b><small>Profile status: {selected.status || 'REGISTERED'}</small></div><label>Research stance for {symbol}<select value={biasByAgent[selectedId]||'UNASSIGNED'} onChange={e=>setBias(selectedId,e.target.value as Bias)}>{biasOptions.map(b=><option key={b}>{b}</option>)}</select></label><button onClick={()=>setSelectedId('')}>CLOSE</button></aside>}

    <footer className="agent-position-foot"><span>Profiles shown: {Math.min(agents.length,550)} · manual session tags: {Object.values(biasByAgent).filter(v=>v!=='UNASSIGNED').length}</span><span>Research-only · no portfolio exposure or execution</span></footer>
  </section>
}
