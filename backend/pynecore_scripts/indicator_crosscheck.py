"""
@pyne
"""
"""Fixed, indicator-only PyneCore script for offline chart research.

This file intentionally contains no strategy orders, broker integration, or live mode.
"""
from pynecore.lib import close, plot, script, ta


@script.indicator(title="MARKET-MIND-AI Indicator Cross-check")
def main():
    plot(ta.sma(close, 20), "SMA20")
    plot(ta.rsi(close, 14), "RSI14")
    plot(ta.atr(14), "ATR14")
