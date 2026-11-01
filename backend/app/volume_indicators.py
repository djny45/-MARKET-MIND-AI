"""Dependency-light OHLCV volume indicators for historical research.

Inputs must be chronological (oldest first). Outputs are descriptive series,
not trading instructions. No external data is fetched and no orders are placed.
"""
from math import isfinite


def _series(**columns):
    if not columns:
        raise ValueError("OHLCV columns are required")
    lengths = {len(v) for v in columns.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
        raise ValueError("OHLCV columns must have equal lengths of at least two")
    result = {}
    for name, values in columns.items():
        xs = [float(x) for x in values]
        if any(not isfinite(x) for x in xs):
            raise ValueError(f"{name} values must be finite")
        result[name] = xs
    n = next(iter(lengths))
    for i in range(n):
        if "high" in result and "low" in result and result["high"][i] < result["low"][i]:
            raise ValueError("high cannot be below low")
        if "volume" in result and result["volume"][i] < 0:
            raise ValueError("volume cannot be negative")
        if "close" in result and result["close"][i] <= 0:
            raise ValueError("close must be positive")
    return result


def _sma(xs, period):
    if period < 1:
        raise ValueError("period must be positive")
    return [sum(xs[max(0, i-period+1):i+1]) / len(xs[max(0, i-period+1):i+1]) for i in range(len(xs))]


def _ema(xs, period):
    if period < 1:
        raise ValueError("period must be positive")
    alpha = 2 / (period + 1)
    out = [xs[0]]
    for value in xs[1:]:
        out.append(alpha * value + (1-alpha) * out[-1])
    return out


def calculate_volume_indicators(high, low, close, volume, period=20):
    """Calculate common volume, flow, and volume-weighted indicators."""
    if period < 1 or period > 10000:
        raise ValueError("period must be between 1 and 10000")
    x = _series(high=high, low=low, close=close, volume=volume)
    h, l, c, v = x["high"], x["low"], x["close"], x["volume"]
    n = len(c)
    if any(h[i] < max(l[i], c[i]) or l[i] > min(h[i], c[i]) for i in range(n)):
        raise ValueError("OHLC values are inconsistent")
    obv, adl, vpt, nvi, pvi = [0.0], [0.0], [0.0], [1000.0], [1000.0]
    mfv, force, eom, typical, pv = [], [], [], [], []
    for i in range(n):
        spread = h[i] - l[i]
        multiplier = 0.0 if spread == 0 else ((c[i]-l[i])-(h[i]-c[i]))/spread
        mfv.append(multiplier * v[i])
        typical.append((h[i]+l[i]+c[i])/3)
        pv.append(typical[-1] * v[i])
        if i:
            direction = 1 if c[i] > c[i-1] else -1 if c[i] < c[i-1] else 0
            obv.append(obv[-1] + direction*v[i])
            adl.append(adl[-1] + mfv[i])
            change = c[i]/c[i-1]-1
            vpt.append(vpt[-1] + change*v[i])
            nvi.append(nvi[-1] * (1+change) if v[i] < v[i-1] else nvi[-1])
            pvi.append(pvi[-1] * (1+change) if v[i] > v[i-1] else pvi[-1])
            force.append((c[i]-c[i-1])*v[i])
            midpoint_now=(h[i]+l[i])/2
            midpoint_prev=(h[i-1]+l[i-1])/2
            box=0.0 if v[i] == 0 or spread == 0 else ((v[i]/spread) / 100000000)
            eom.append(0.0 if box == 0 else (midpoint_now-midpoint_prev)/box)
        else:
            force.append(None)
            eom.append(None)
    cmf=[]
    mfi=[]
    for i in range(n):
        start=max(0,i-period+1)
        vol=sum(v[start:i+1])
        cmf.append(sum(mfv[start:i+1])/vol if vol else 0.0)
        pos=neg=0.0
        for j in range(max(1,start),i+1):
            flow=typical[j]*v[j]
            if typical[j] > typical[j-1]: pos += flow
            elif typical[j] < typical[j-1]: neg += flow
        mfi.append(100.0 if neg == 0 and pos > 0 else 0.0 if pos == 0 else 100-100/(1+pos/neg))
    vwap=[]
    cum_pv=cum_v=0.0
    for value, vol in zip(typical,v):
        cum_pv += value*vol
        cum_v += vol
        vwap.append(cum_pv/cum_v if cum_v else None)
    avgvol=_sma(v,period)
    rvol=[vol/avg if avg else None for vol,avg in zip(v,avgvol)]
    fast=_ema(v,max(1,period//2))
    slow=_ema(v,period)
    volume_osc=[(a-b)/b*100 if b else 0.0 for a,b in zip(fast,slow)]
    vroc=[None if i < period or v[i-period] == 0 else (v[i]/v[i-period]-1)*100 for i in range(n)]
    # Money-flow oscillator: EMA of accumulation/distribution flow difference.
    ad_fast=_ema(adl,max(1,period//2))
    ad_slow=_ema(adl,period)
    chaikin=[a-b for a,b in zip(ad_fast,ad_slow)]
    return {
        "obv": obv, "adl": adl, "chaikin_oscillator": chaikin,
        "cmf": cmf, "mfi": mfi, "force_index": force,
        "ease_of_movement": eom, "vpt": vpt, "nvi": nvi, "pvi": pvi,
        "vwap": vwap, "relative_volume": rvol,
        "volume_oscillator": volume_osc, "volume_rate_of_change": vroc,
        "volume_sma": avgvol,
        "metadata": {"period": period, "bars": n, "ordering": "oldest_to_newest",
                     "purpose": "historical_descriptive_research_only"},
    }
