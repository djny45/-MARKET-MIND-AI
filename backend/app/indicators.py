"""Dependency-light deterministic indicators over chronological numeric observations."""
from math import sqrt, isfinite
def _valid(values, minimum=1):
 try:
  xs=[float(x) for x in values]
 except (TypeError, ValueError, OverflowError) as exc:
  raise ValueError("values must be finite numeric observations") from exc
 if not all(isfinite(x) for x in xs):
  raise ValueError("values must be finite numeric observations")
 if len(xs)<minimum: raise ValueError(f"At least {minimum} observations are required.")
 return xs
def sma(values,period):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 out=[]
 for i in range(len(xs)):
  window=xs[max(0,i-p+1):i+1]
  scale=max(abs(x) for x in window)
  mean=0.0 if scale==0 else scale*(sum(x/scale for x in window)/len(window))
  if not isfinite(mean): raise ValueError("moving average must be finite")
  out.append(mean)
 return out
def ema(values,period):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 a=2/(p+1); out=[xs[0]]
 for x in xs[1:]:
  previous=out[-1]
  scale=max(abs(x),abs(previous))
  value=0.0 if scale==0 else scale*(a*(x/scale)+(1-a)*(previous/scale))
  if not isfinite(value): raise ValueError("exponential moving average must be finite")
  out.append(value)
 return out
def returns(values):
 xs=_valid(values,2)
 if any(x==0 for x in xs[:-1]): raise ValueError("zero denominator in price series")
 out=[]
 for i in range(1,len(xs)):
  result=xs[i]/xs[i-1]-1
  if not isfinite(result):
   raise ValueError("return is non-finite for the supplied price observations")
  out.append(result)
 return out
def rsi(values,period=14):
 rs=returns(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 if len(rs)<p: return [None]*len(rs)
 gains=[max(x,0) for x in rs]; losses=[max(-x,0) for x in rs]
 ag=sum(gains[:p])/p; al=sum(losses[:p])/p; out=[None]*(p-1)
 out.append(100.0 if al==0 else 100-100/(1+ag/al))
 for i in range(p,len(rs)):
  ag=(ag*(p-1)+gains[i])/p; al=(al*(p-1)+losses[i])/p
  out.append(100.0 if al==0 else 100-100/(1+ag/al))
 return out
def macd(values,fast=12,slow=26,signal=9):
 line=[a-b for a,b in zip(ema(values,fast),ema(values,slow))]
 if not all(isfinite(x) for x in line): raise ValueError("MACD line must be finite")
 sig=ema(line,signal)
 histogram=[a-b for a,b in zip(line,sig)]
 if not all(isfinite(x) for x in histogram): raise ValueError("MACD histogram must be finite")
 return {"macd":line,"signal":sig,"histogram":histogram}
def bollinger(values,period=20,deviations=2):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 mid=sma(xs,p); upper=[]; lower=[]
 for i,m in enumerate(mid):
  w=xs[max(0,i-p+1):i+1]
  scale=max(abs(x) for x in w)
  if scale==0:
   sd=0.0
  else:
   normalized_mean=m/scale
   normalized_sd=sqrt(sum((x/scale-normalized_mean)**2 for x in w)/len(w))
   sd=scale*normalized_sd
  up=m+deviations*sd; lo=m-deviations*sd
  if not all(isfinite(value) for value in (sd,up,lo)):
   raise ValueError("Bollinger bands must be finite")
  upper.append(up); lower.append(lo)
 return {"middle":mid,"upper":upper,"lower":lower}
def realized_volatility(prices,annualization=None):
 rs=returns(prices)
 if len(rs)<2: raise ValueError("At least two returns are required.")
 scale=max(abs(x) for x in rs)
 if scale==0:
  volatility=0.0
 else:
  normalized=[x/scale for x in rs]
  mean=sum(normalized)/len(normalized)
  variance=sum((x-mean)**2 for x in normalized)/(len(normalized)-1)
  volatility=scale*sqrt(variance)
 if not isfinite(volatility):
  raise ValueError("volatility must be finite")
 out={"per_observation":volatility,"observations":len(rs)}
 if annualization is not None:
  try:
   annualization=float(annualization)
  except (TypeError,ValueError,OverflowError) as exc:
   raise ValueError("annualization must be finite and positive") from exc
  if not isfinite(annualization) or annualization<=0:
   raise ValueError("annualization must be finite and positive")
  annualized=volatility*sqrt(annualization)
  if not isfinite(annualized):
   raise ValueError("annualized volatility must be finite")
  out["annualized"]=annualized
 return out
