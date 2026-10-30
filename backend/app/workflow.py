from collections import defaultdict, deque
from typing import Any
import math
from . import indicators

NODE_TYPES = {
 "market_input":{"type":"market_input","label":"Market Input","category":"data","inputs":[],"outputs":["data"],"description":"Accept normalized numeric observations."},
 "data_quality":{"type":"data_quality","label":"Data Quality","category":"validation","inputs":["data"],"outputs":["data","quality"],"description":"Validate numeric observations."},
 "sma":{"type":"sma","label":"Simple Moving Average","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate SMA."},
 "ema":{"type":"ema","label":"Exponential Moving Average","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate EMA."},
 "rsi":{"type":"rsi","label":"Relative Strength Index","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate RSI."},
 "macd":{"type":"macd","label":"MACD","category":"technical","inputs":["data"],"outputs":["macd","signal","histogram"],"description":"Calculate MACD line, signal and histogram."},
 "bollinger":{"type":"bollinger","label":"Bollinger Bands","category":"technical","inputs":["data"],"outputs":["middle","upper","lower"],"description":"Calculate Bollinger bands."},
 "returns":{"type":"returns","label":"Returns","category":"quant","inputs":["data"],"outputs":["series","summary"],"description":"Calculate simple period returns."},
 "volatility":{"type":"volatility","label":"Realized Volatility","category":"quant","inputs":["data"],"outputs":["value"],"description":"Estimate sample volatility of returns."},
 "research_summary":{"type":"research_summary","label":"Research Summary","category":"intelligence","inputs":["data"],"outputs":["report"],"description":"Create a descriptive evidence summary."},
}
def _node_id(node): return str(node.get("id",""))
def execute_workflow(nodes:list[dict[str,Any]],edges:list[dict[str,Any]],inputs:dict[str,Any]):
 by_id={_node_id(n):n for n in nodes}
 if not nodes or any(not k for k in by_id) or len(by_id)!=len(nodes): raise ValueError("Workflow must contain uniquely identified nodes.")
 incoming,outgoing=defaultdict(list),defaultdict(list); indegree={k:0 for k in by_id}
 for edge in edges:
  source,target=str(edge.get("source","")),str(edge.get("target",""))
  if source not in by_id or target not in by_id: raise ValueError("An edge references a missing node.")
  outgoing[source].append(target); incoming[target].append(source); indegree[target]+=1
 queue=deque(k for k,d in indegree.items() if d==0); order=[]
 while queue:
  current=queue.popleft(); order.append(current)
  for target in outgoing[current]:
   indegree[target]-=1
   if indegree[target]==0: queue.append(target)
 if len(order)!=len(nodes): raise ValueError("Workflow contains a cycle.")
 results={}
 for node_id in order:
  node=by_id[node_id]; kind=node.get("type")
  if kind not in NODE_TYPES: raise ValueError(f"Unsupported node type: {kind}")
  upstream=[results[s] for s in incoming[node_id]]
  payload=upstream[-1] if upstream else inputs.get(node_id,inputs.get("data",[]))
  results[node_id]=_run_node(kind,payload,node.get("data",{}) or {})
 return {"status":"completed","execution_order":order,"results":results,"research_only":True}
def _numbers(payload):
 if isinstance(payload,dict):
  for key in ("values","close","series"):
   if isinstance(payload.get(key),list): payload=payload[key]; break
  else:
   if isinstance(payload.get("data"),dict): return _numbers(payload["data"])
   if isinstance(payload.get("value"),(int,float)): payload=[payload["value"]]
   else: raise ValueError("Expected numeric values, close or series.")
 if not isinstance(payload,list): raise ValueError("Expected a list of numeric values.")
 try: values=[float(x) for x in payload]
 except (TypeError,ValueError) as exc: raise ValueError("Dataset contains non-numeric values.") from exc
 if not all(math.isfinite(x) for x in values): raise ValueError("Dataset contains non-finite values.")
 return values
def _run_node(kind,payload,params):
 if kind=="market_input": return {"values":_numbers(params.get("values",payload))}
 if kind=="data_quality":
  values=_numbers(payload)
  return {"data":{"values":values},"quality":{"rows":len(values),"missing":0,"finite":True,"status":"pass" if values else "empty"}}
 if kind in ("sma","ema","rsi","macd","bollinger"):
  values=_numbers(payload); period=max(1,int(params.get("period",14)))
  if kind=="sma": return {"series":indicators.sma(values,period),"period":period}
  if kind=="ema": return {"series":indicators.ema(values,period),"period":period}
  if kind=="rsi": return {"series":indicators.rsi(values,period),"period":period}
  if kind=="macd": return indicators.macd(values)
  return indicators.bollinger(values,period)
 if kind=="returns":
  values=_numbers(payload); series=indicators.returns(values)
  return {"series":series,"summary":{"observations":len(series),"mean":sum(series)/len(series) if series else None}}
 if kind=="volatility": return indicators.realized_volatility(_numbers(payload))
 if kind=="research_summary":
  values=_numbers(payload)
  return {"report":{"observations":len(values),"first":values[0] if values else None,"last":values[-1] if values else None,"scope":"Descriptive calculations only; not a trade recommendation."}}
 raise ValueError(f"No handler for {kind}")
