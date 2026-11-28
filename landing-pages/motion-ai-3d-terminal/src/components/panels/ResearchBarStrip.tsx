"use client";

import { formatUtcClock } from "@/lib/ui";
import type { ResearchBarsResult } from "@/lib/researchBars";

/**
 * Optional research-feed strip. Rendered only when the server opted in via
 * MARKET_MIND_RESEARCH_DB. Every label states provenance and staleness; this
 * is publicly sourced 15m research data, never execution-grade live prices.
 */
export function ResearchBarStrip({ data }: { data: ResearchBarsResult }) {
  if (!data.enabled) return null;
  const latest = new Map<string, (typeof data.bars)[number]>();
  for (const bar of data.bars) {
    if (!latest.has(bar.symbol)) latest.set(bar.symbol, bar);
  }
  return (
    <div
      role="status"
      className="rounded-xl border border-amber-400/25 bg-amber-400/[0.06] px-3 py-2"
      title={data.detail}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[8.5px] uppercase tracking-[0.14em]">
        <span className="text-amber-200/90">
          research bars · binance-public · 15m · not live/execution-grade
        </span>
        {data.stale ? (
          <span className="text-rose-300">stale — last retrieval older than 60 min</span>
        ) : null}
        {data.asOf ? <span className="text-muted">retrieved {formatUtcClock(data.asOf)} UTC</span> : null}
        <span className="text-muted/70">research-only · no trading</span>
      </div>
      {data.available ? (
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] tabular-nums text-ink/90">
          {[...latest.entries()].map(([symbol, bar]) => (
            <span key={symbol}>
              {symbol} <span className="text-amber-200/90">{bar.close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              <span className="ml-1 text-muted/70">{formatUtcClock(bar.timestamp)}</span>
            </span>
          ))}
        </div>
      ) : (
        <div className="mt-1 font-mono text-[9px] text-muted">{data.detail}</div>
      )}
    </div>
  );
}
