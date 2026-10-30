"""Descriptive portfolio-style statistics for research datasets, not trade advice."""
from math import sqrt
from .indicators import returns

def _finite(values, name):
    xs=[float(v) for v in values]
    if not xs: raise ValueError(f"{name} must not be empty")
    if any(not __import__("math").isfinite(x) for x in xs):
        raise ValueError(f"{name} must contain finite numbers")
    return xs

def max_drawdown(prices):
    xs=_finite(prices,"prices")
    if any(x<=0 for x in xs): raise ValueError("prices must be positive")
    peak=xs[0]; worst=0.0
    for value in xs:
        peak=max(peak,value)
        worst=min(worst,value/peak-1.0)
    return worst

def performance_metrics(prices, benchmark=None, periods_per_year=None, risk_free_rate=0.0):
    xs=_finite(prices,"prices")
    if len(xs)<3: raise ValueError("At least three prices are required")
    if any(x<=0 for x in xs): raise ValueError("prices must be positive")
    rs=returns(xs); mean=sum(rs)/len(rs)
    variance=sum((x-mean)**2 for x in rs)/(len(rs)-1)
    vol=sqrt(variance)
    downside=[min(x,0.0) for x in rs]
    downside_dev=sqrt(sum(x*x for x in downside)/len(downside))
    excess=mean-float(risk_free_rate)
    out={
      "observations":len(xs),"return_observations":len(rs),
      "cumulative_return":xs[-1]/xs[0]-1.0,
      "mean_period_return":mean,"sample_volatility":vol,
      "max_drawdown":max_drawdown(xs),
      "sharpe_per_period":excess/vol if vol else None,
      "sortino_per_period":excess/downside_dev if downside_dev else None,
      "annualized_sharpe":None,"annualized_volatility":None,
      "beta":None,"correlation_to_benchmark":None,
      "scope":"Historical descriptive statistics; not a forecast or recommendation."
    }
    if periods_per_year is not None:
      p=float(periods_per_year)
      if p<=0: raise ValueError("periods_per_year must be positive")
      out["annualized_sharpe"]=(excess/vol)*sqrt(p) if vol else None
      out["annualized_volatility"]=vol*sqrt(p)
    if benchmark is not None:
      br=returns(_finite(benchmark,"benchmark"))
      if len(br)!=len(rs): raise ValueError("benchmark must have the same number of return observations")
      bm=sum(br)/len(br)
      bv=sum((x-bm)**2 for x in br)/(len(br)-1)
      cov=sum((a-mean)*(b-bm) for a,b in zip(rs,br))/(len(rs)-1)
      out["beta"]=cov/bv if bv else None
      out["correlation_to_benchmark"]=cov/(vol*sqrt(bv)) if vol and bv else None
    return out
