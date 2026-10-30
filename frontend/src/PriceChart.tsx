import { useEffect, useRef } from 'react'
import { createChart, ColorType, LineSeries, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts'

type Props = { values: number[] }
export default function PriceChart({values}:Props) {
 const host=useRef<HTMLDivElement|null>(null)
 const chartRef=useRef<IChartApi|null>(null)
 const seriesRef=useRef<ISeriesApi<'Line'>|null>(null)
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
  const series=chart.addSeries(LineSeries,{color:'#d6a34e',lineWidth:2,priceLineVisible:false,lastValueVisible:true})
  chartRef.current=chart;seriesRef.current=series
  const resize=new ResizeObserver(entries=>{for(const entry of entries){chart.applyOptions({width:entry.contentRect.width,height:entry.contentRect.height})}})
  resize.observe(host.current)
  return ()=>{resize.disconnect();chart.remove();chartRef.current=null;seriesRef.current=null}
 },[])
 useEffect(()=>{
  if(!seriesRef.current || values.length===0) return
  const now=new Date()
  const data=values.map((value,index)=>{
   const d=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()-values.length+index+1))
   return {time:d.toISOString().slice(0,10) as Time,value}
  })
  seriesRef.current.setData(data);chartRef.current?.timeScale().fitContent()
 },[values])
 return <div className="chart-shell"><div className="chart-heading"><div><b>PRICE SERIES</b><span> · SAMPLE INPUT DATA</span></div><small>NOT A LIVE QUOTE</small></div><div ref={host} className="chart-host"/></div>
}
