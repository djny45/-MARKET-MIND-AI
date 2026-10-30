import { useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickSeries, LineSeries, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts'

type Bar = {timestamp:string;open:number;high:number;low:number;close:number;source?:string;status?:string;retrieved_at?:string}
type Cluster = {side:string;mean_price:number;lower_price:number;upper_price:number;touch_count:number;pivot_timestamps:(string|null)[]}
type Props = {values?:number[];bars?:Bar[];selectedCluster?:Cluster|null;interval?:string}
function toTime(value:string):Time {
 const date=new Date(value)
 return Math.floor(date.getTime()/1000) as Time
}
export default function PriceChart({values=[],bars=[],selectedCluster=null,interval=''}:Props) {
 const host=useRef<HTMLDivElement|null>(null)
 const chartRef=useRef<IChartApi|null>(null)
 const lineRef=useRef<ISeriesApi<'Line'>|null>(null)
 const candleRef=useRef<ISeriesApi<'Candlestick'>|null>(null)
 useEffect(()=>{
  if(!host.current) return
  const chart=createChart(host.current,{
   autoSize:true,
   layout:{background:{type:ColorType.Solid,color:'#10161d'},textColor:'#9aa7b5',fontFamily:'DM Mono, monospace'},
   grid:{vertLines:{color:'#202a35'},horzLines:{color:'#202a35'}},
   rightPriceScale:{borderColor:'#303b47'},
   timeScale:{borderColor:'#303b47',timeVisible:true,secondsVisible:false},
   crosshair:{vertLine:{color:'#b88b46',labelBackgroundColor:'#8b6736'},horzLine:{color:'#b88b46',labelBackgroundColor:'#8b6736'}},
  })
  const candle=chart.addSeries(CandlestickSeries,{upColor:'#62b58e',downColor:'#d77970',borderUpColor:'#62b58e',borderDownColor:'#d77970',wickUpColor:'#62b58e',wickDownColor:'#d77970'})
  const line=chart.addSeries(LineSeries,{color:'#d6a34e',lineWidth:2,priceLineVisible:false,lastValueVisible:true})
  chartRef.current=chart;candleRef.current=candle;lineRef.current=line
  const resize=new ResizeObserver(entries=>{for(const entry of entries){chart.applyOptions({width:entry.contentRect.width,height:entry.contentRect.height})}})
  resize.observe(host.current)
  return ()=>{resize.disconnect();chart.remove();chartRef.current=null;candleRef.current=null;lineRef.current=null}
 },[])
 useEffect(()=>{
  if(!chartRef.current||!candleRef.current||!lineRef.current)return
  if(bars.length){
   const sorted=[...bars].filter(b=>Number.isFinite(Date.parse(b.timestamp))).sort((a,b)=>Date.parse(a.timestamp)-Date.parse(b.timestamp))
   candleRef.current.setData(sorted.map(b=>({time:toTime(b.timestamp),open:b.open,high:b.high,low:b.low,close:b.close})))
   lineRef.current.setData([])
   if(selectedCluster&&sorted.length){
    const first=toTime(sorted[0].timestamp),last=toTime(sorted[sorted.length-1].timestamp)
    lineRef.current.setData([{time:first,value:selectedCluster.mean_price},{time:last,value:selectedCluster.mean_price}])
   }
   chartRef.current.timeScale().fitContent()
  } else if(values.length){
   candleRef.current.setData([])
   const now=new Date()
   lineRef.current.setData(values.map((value,index)=>{
    const d=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()-values.length+index+1))
    return {time:d.toISOString().slice(0,10) as Time,value}
   }))
   chartRef.current.timeScale().fitContent()
  }
 },[values,bars,selectedCluster])
 const source=bars.length?Array.from(new Set(bars.map(b=>b.source||'unknown'))).join(', '):'manual / synthetic input'
 const status=bars.length?Array.from(new Set(bars.map(b=>b.status||'unknown'))).join(', '):'not historical market data'
 return <div className="chart-shell"><div className="chart-heading"><div><b>{bars.length?'STORED OHLCV HISTORY':'PRICE SERIES'}</b><span> · {interval||'SAMPLE INPUT'}</span></div><small>{bars.length?source+' · '+status:'NOT A LIVE QUOTE'}</small></div><div ref={host} className="chart-host"/></div>
}
