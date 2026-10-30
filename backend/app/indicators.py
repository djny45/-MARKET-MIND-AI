"""Dependency-light deterministic indicators over chronological numeric observations."""
from math import sqrt
def _valid(values, minimum=1):
 xs=[float(x) for x in values]
 if len(xs)<minimum: raise ValueError(f"At least {minimum} observations are required.")
 return xs
def sma(values,period):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 return [sum(xs[max(0,i-p+1):i+1])/len(xs[max(0,i-p+1):i+1]) for i in range(len(xs))]
def ema(values,period):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 a=2/(p+1); out=[xs[0]]
 for x in xs[1:]: out.append(a*x+(1-a)*out[-1])
 return out
def returns(values):
 xs=_valid(values,2)
 if any(x==0 for x in xs[:-1]): raise ValueError("zero denominator in price series")
 return [xs[i]/xs[i-1]-1 for i in range(1,len(xs))]
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
 line=[a-b for a,b in zip(ema(values,fast),ema(values,slow))]; sig=ema(line,signal)
 return {"macd":line,"signal":sig,"histogram":[a-b for a,b in zip(line,sig)]}
def bollinger(values,period=20,deviations=2):
 xs=_valid(values); p=int(period)
 if p<1: raise ValueError("period must be positive")
 mid=sma(xs,p); upper=[]; lower=[]
 for i,m in enumerate(mid):
  w=xs[max(0,i-p+1):i+1]; sd=sqrt(sum((x-m)**2 for x in w)/len(w))
  upper.append(m+deviations*sd); lower.append(m-deviations*sd)
 return {"middle":mid,"upper":upper,"lower":lower}
def realized_volatility(prices,annualization=None):
 rs=returns(prices)
 if len(rs)<2: raise ValueError("At least two returns are required.")
 mean=sum(rs)/len(rs); var=sum((x-mean)**2 for x in rs)/(len(rs)-1)
 out={"per_observation":sqrt(var),"observations":len(rs)}
 if annualization is not None:
  if annualization<=0: raise ValueError("annualization must be positive")
  out["annualized"]=sqrt(var*annualization)
 return out
