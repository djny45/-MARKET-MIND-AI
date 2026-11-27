"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ReactiveCore } from "@/components/ReactiveCore";
import { AgentDrawer } from "@/components/AgentDrawer";
import { Sparkline } from "@/components/Sparkline";
import { AgentDirectory } from "@/components/panels/AgentDirectory";
import { ConsensusBoard } from "@/components/panels/ConsensusBoard";
import { CoreTelemetry } from "@/components/panels/CoreTelemetry";
import { MarketStrip, TickerTape } from "@/components/panels/MarketStrip";
import { SignalFeed } from "@/components/panels/SignalFeed";
import { Watchlist } from "@/components/panels/Watchlist";
import { FOCUS_COLOR, formatSignedPct } from "@/lib/ui";
import { formatCompact, formatPrice, type MarketKey } from "@/lib/market";
import type { InstrumentView, MarketSnapshot, SignalView } from "@/lib/types";
import type { BackendSnapshot } from "@/lib/marketMindAdapter";

const CLOCKS = [
  { label: "NEW YORK", zone: "America/New_York" },
  { label: "MUMBAI", zone: "Asia/Kolkata" },
  { label: "LONDON", zone: "Europe/London" },
];

function formatZone(date: Date, zone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function TerminalShell({
  initialSnapshot,
  demoReason = null,
}: {
  initialSnapshot: MarketSnapshot;
  demoReason?: string | null;
}) {
  const [snapshot, setSnapshot] = useState<MarketSnapshot>(initialSnapshot);
  const [selectedSymbol, setSelectedSymbol] = useState(
    initialSnapshot.instruments.find((item) => item.market === "gold")?.symbol ??
      initialSnapshot.instruments[0]?.symbol ??
      "",
  );
  const [selectedMarket, setSelectedMarket] = useState<MarketKey>("gold");
  const [scanning, setScanning] = useState(false);
  const [autoScan, setAutoScan] = useState(true);
  const [drawerAgent, setDrawerAgent] = useState<number | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const [connection, setConnection] = useState<"simulated" | "stale" | "offline">("simulated");
  const [backend, setBackend] = useState<BackendSnapshot | null>(null);
  const scanningRef = useRef(false);

  const selectedInstrument = useMemo(
    () => snapshot.instruments.find((item) => item.symbol === selectedSymbol) ?? snapshot.instruments[0],
    [selectedSymbol, snapshot.instruments],
  );

  useEffect(() => {
    const initial = setTimeout(() => setNow(new Date()), 0);
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const poll = async () => {
      try {
        const response = await fetch("/api/market", { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("snapshot failed");
        const payload = (await response.json()) as MarketSnapshot;
        if (cancelled) return;
        setSnapshot(payload);
        setConnection("simulated");
      } catch (error) {
        if ((error as Error).name === "AbortError" || cancelled) return;
        setConnection((current) => (current === "simulated" ? "stale" : "offline"));
      }
    };

    const timer = setInterval(poll, 3500);
    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const check = async () => {
      try {
        const response = await fetch("/api/backend", {
          signal: controller.signal,
          cache: "no-store",
        });
        if (response.ok && !cancelled) {
          setBackend((await response.json()) as BackendSnapshot);
        }
      } catch {
        /* backend status is informational; never break the terminal */
      }
    };
    void check();
    const timer = setInterval(() => void check(), 30_000);
    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const runScan = useCallback(async () => {
    if (scanningRef.current) return;
    scanningRef.current = true;
    setScanning(true);
    try {
      const response = await fetch("/api/scan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ count: 3 }),
      });
      if (!response.ok) throw new Error("scan failed");
      const payload = (await response.json()) as { signals: SignalView[]; consensus: MarketSnapshot["consensus"] };
      setSnapshot((previous) => ({
        ...previous,
        signals: [...payload.signals, ...previous.signals].slice(0, 24),
        consensus: payload.consensus.length > 0 ? payload.consensus : previous.consensus,
        asOf: new Date().toISOString(),
      }));
      setConnection("simulated");
    } catch (error) {
      console.error(error);
    } finally {
      scanningRef.current = false;
      setScanning(false);
    }
  }, []);

  const scanRef = useRef(runScan);

  useEffect(() => {
    scanRef.current = runScan;
  }, [runScan]);

  useEffect(() => {
    if (!autoScan) return;
    const timer = setInterval(() => {
      void scanRef.current();
    }, 11_000);
    return () => clearInterval(timer);
  }, [autoScan]);

  const handleSelectInstrument = useCallback((instrument: InstrumentView) => {
    setSelectedSymbol(instrument.symbol);
    setSelectedMarket(instrument.market);
  }, []);

  const handleMarketChange = useCallback(
    (market: MarketKey) => {
      setSelectedMarket(market);
      const instrument = snapshot.instruments.find((item) => item.market === market);
      if (instrument) setSelectedSymbol(instrument.symbol);
    },
    [snapshot.instruments],
  );

  const agentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const row of snapshot.agents.byFocus) counts[row.focus] = row.count;
    return counts;
  }, [snapshot.agents.byFocus]);

  const sessionStatus = snapshot.sessions;
  const activeSessions = sessionStatus.filter((session) => session.status === "open").length;

  return (
    <div className="relative min-h-screen">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-void/90 backdrop-blur-xl">
        <div className="mx-auto max-w-[1720px] px-3 lg:px-5">
          <div className="flex items-center gap-3 py-2">
            <div className="flex items-center gap-2.5">
              <span className="relative grid h-9 w-9 place-items-center">
                <svg viewBox="0 0 40 40" className="h-9 w-9">
                  <defs>
                    <linearGradient id="logo-iris" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor="#e0d7ff" />
                      <stop offset="100%" stopColor="#4fe6d8" />
                    </linearGradient>
                  </defs>
                  <path d="M20 2 L35 11 L35 29 L20 38 L5 29 L5 11 Z" fill="none" stroke="url(#logo-iris)" strokeWidth="1.2" />
                  <path d="M20 9 L29 14.5 L29 25.5 L20 31 L11 25.5 L11 14.5 Z" fill="rgba(167,139,250,0.12)" stroke="rgba(167,139,250,0.5)" strokeWidth="0.8" />
                  <circle cx="20" cy="20" r="3" fill="#e0d7ff" />
                  <circle cx="20" cy="20" r="6.5" fill="none" stroke="rgba(79,230,216,0.5)" strokeWidth="0.7" />
                </svg>
                <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-br from-iris/30 to-aqua/20 blur-xl" />
              </span>
              <div>
                <h1 className="font-mono text-[13px] font-semibold leading-none tracking-[0.18em] text-ink uppercase">
                  MARKET MIND <span className="text-iris">AI</span><span className="ml-1 text-aqua/70">Ω</span>
                </h1>
                <p className="mt-1 hidden font-mono text-[8px] tracking-[0.2em] text-muted uppercase sm:block">
                  550-agent multi-market intelligence terminal
                </p>
              </div>
            </div>

            <div className="ml-2 hidden items-center gap-1.5 lg:flex">
              {CLOCKS.map((clock) => (
                <div key={clock.label} className="rounded-sm border border-line/70 bg-panel/70 px-2 py-1">
                  <div className="font-mono text-[7.5px] tracking-[0.16em] text-muted/80 uppercase">{clock.label}</div>
                  <div className="font-mono text-[10.5px] tabular-nums text-ink/85">
                    {now ? formatZone(now, clock.zone) : "--:--:--"}
                  </div>
                </div>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-1.5">
              <div
                className="hidden items-center gap-1.5 rounded-sm border border-line/70 bg-panel/70 px-2 py-1 xl:flex"
                title={backend?.detail ?? "Optional MARKET-MIND-AI backend adapter"}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background:
                      backend?.status === "connected"
                        ? "#5fe6a6"
                        : backend?.status === "disabled"
                          ? "#7d8994"
                          : "#a78bfa",
                  }}
                />
                <span className="font-mono text-[8.5px] tracking-[0.14em] text-muted uppercase">
                  backend {backend?.status ?? "checking"}
                </span>
              </div>
              <div className="hidden items-center gap-1.5 rounded-sm border border-line/70 bg-panel/70 px-2 py-1 sm:flex">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-mint opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-mint" />
                </span>
                <span className="font-mono text-[9px] tracking-[0.12em] text-ink/80">
                  {snapshot.agents.total.toLocaleString()} AGENTS
                </span>
              </div>
              <div className="hidden items-center gap-1.5 rounded-sm border border-line/70 bg-panel/70 px-2 py-1 md:flex">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: connection === "simulated" ? "#a78bfa" : connection === "stale" ? "#a78bfa" : "#fd7f95",
                    boxShadow: `0 0 8px ${connection === "simulated" ? "#a78bfa" : "#a78bfa"}`,
                  }}
                />
                <span className="font-mono text-[8.5px] tracking-[0.14em] text-muted uppercase">
                  {connection === "simulated" ? "simulated feed" : connection === "stale" ? "resyncing" : "offline"}
                </span>
              </div>
              <div className="hidden rounded-sm border border-line/70 bg-panel/70 px-2 py-1 sm:block">
                <div className="font-mono text-[7.5px] tracking-[0.16em] text-muted/80 uppercase">Sessions</div>
                <div className="font-mono text-[10.5px] tabular-nums text-iris">
                  {activeSessions}/4 <span className="text-muted/70">open</span>
                </div>
              </div>
              <button
                type="button"
                onClick={runScan}
                disabled={scanning}
                className="group relative overflow-hidden rounded-sm border border-iris/50 bg-gradient-to-b from-iris/20 to-iris/5 px-2.5 py-[7px] font-mono text-[9px] tracking-[0.16em] text-iris-bright uppercase transition-all hover:border-iris hover:shadow-[0_0_24px_-6px_rgba(242,196,107,0.6)] disabled:opacity-60"
              >
                {scanning ? "swarm scanning…" : "deploy swarm"}
              </button>
            </div>
          </div>
        </div>
        <TickerTape instruments={snapshot.instruments} />
      </header>

      {demoReason !== null && (
        <div
          role="status"
          className="sticky top-[57px] z-30 border-b border-amber-400/30 bg-amber-400/10 px-3 py-2 text-center font-mono text-[9px] uppercase tracking-[0.14em] text-amber-200"
        >
          read-only demo mode · database unavailable · synthetic sample data · not live market data
        </div>
      )}

      <main className="mx-auto max-w-[1720px] space-y-3 px-3 py-3 lg:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="rounded-sm border border-iris/30 bg-iris/[0.07] px-1.5 py-[2px] font-mono text-[8.5px] tracking-[0.16em] text-iris uppercase">
              research · simulated data
            </span>
            <span className="font-mono text-[8.5px] tracking-[0.12em] text-muted uppercase">
              gold · forex · usa · india · 550 generated profiles
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[8.5px] tracking-[0.1em] text-muted uppercase">
            <span className="hidden sm:inline">snapshot {new Date(snapshot.asOf).toISOString().slice(11, 19)} utc</span>
            <span className="text-line-bright">|</span>
            <span className="text-iris/80">market mind core v4.2.1</span>
          </div>
        </div>

        <MarketStrip
          sessions={snapshot.sessions}
          instruments={snapshot.instruments}
          consensus={snapshot.consensus}
          agentCounts={agentCounts}
          selectedMarket={selectedMarket}
          onMarketChange={handleMarketChange}
        />

        <div className="grid grid-cols-12 gap-3">
          <div className="order-2 col-span-12 xl:order-1 xl:col-span-3">
            <Watchlist
              instruments={snapshot.instruments}
              sessions={snapshot.sessions}
              selectedSymbol={selectedInstrument?.symbol ?? ""}
              selectedMarket={selectedMarket}
              onSelect={handleSelectInstrument}
              onMarketChange={handleMarketChange}
            />
          </div>
          <div className="order-1 col-span-12 space-y-3 xl:order-2 xl:col-span-6">
            <ReactiveCore
              instrument={selectedInstrument}
              stats={snapshot.agents}
              consensus={snapshot.consensus}
              signals={snapshot.signals}
              selectedMarket={selectedMarket}
              onMarketChange={handleMarketChange}
              onScan={runScan}
              scanning={scanning}
              autoScan={autoScan}
              onToggleAutoScan={() => setAutoScan((value) => !value)}
            />
            <CoreTelemetry
              stats={snapshot.agents}
              leaderboard={snapshot.leaderboard}
              signals={snapshot.signals}
              onOpenAgent={setDrawerAgent}
            />
          </div>
          <div className="order-3 col-span-12 space-y-3 xl:col-span-3">
            <ConsensusBoard consensus={snapshot.consensus} stats={snapshot.agents} focus={selectedMarket} />
            {selectedInstrument ? (
              <AssetCard instrument={selectedInstrument} onOpenDesk={() => handleMarketChange(selectedInstrument.market)} />
            ) : null}
          </div>
        </div>

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 lg:col-span-5">
            <SignalFeed
              signals={snapshot.signals}
              onOpenAgent={setDrawerAgent}
              onScan={runScan}
              scanning={scanning}
              autoScan={autoScan}
              onToggleAutoScan={() => setAutoScan((value) => !value)}
            />
          </div>
          <div className="col-span-12 lg:col-span-7">
            <AgentDirectory onOpenAgent={setDrawerAgent} agentTotal={snapshot.agents.total} />
          </div>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 py-3 font-mono text-[8.5px] tracking-[0.12em] text-muted/70 uppercase">
          <span>
            market mind ai · {demoReason !== null ? "synthetic demo data (no database)" : "simulated market data"} · 550 generated agent profiles · <span className="text-muted/50">not live data · not verified performance · not investment advice</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="text-mint/80">{snapshot.agents.total.toLocaleString()} agents</span>
            <span className="text-line-bright">/</span>
            <span className="text-aqua/80">{snapshot.agents.totalSignals.toLocaleString()} signals logged</span>
            <span className="text-line-bright">/</span>
            <span>render: reactive 3d swarm</span>
          </span>
        </footer>
      </main>

      <AgentDrawer agentId={drawerAgent} onClose={() => setDrawerAgent(null)} />
    </div>
  );
}

function AssetCard({ instrument, onOpenDesk }: { instrument: InstrumentView; onOpenDesk: () => void }) {
  const accent = FOCUS_COLOR[instrument.market] ?? "#a78bfa";
  const positive = instrument.changePct >= 0;
  const position = Math.max(
    0,
    Math.min(100, ((instrument.price - instrument.dayLow) / Math.max(0.0000001, instrument.dayHigh - instrument.dayLow)) * 100),
  );

  return (
    <div className="panel overflow-hidden rounded-xl">
      <div className="flex items-center justify-between border-b border-line/70 px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-[2px] rounded-full" style={{ background: accent, boxShadow: `0 0 8px ${accent}` }} />
          <span className="font-mono text-[9.5px] tracking-[0.16em] text-ink/90 uppercase">Asset telemetry</span>
        </div>
        <button
          type="button"
          onClick={onOpenDesk}
          className="font-mono text-[8px] tracking-[0.12em] uppercase"
          style={{ color: accent }}
        >
          {instrument.market} desk ↗
        </button>
      </div>
      <div className="px-3 py-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-mono text-[13px] font-medium tracking-wide text-ink">{instrument.symbol}</div>
            <div className="font-mono text-[8.5px] tracking-[0.08em] text-muted uppercase">
              {instrument.name} · {instrument.unit}
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[15px] tabular-nums" style={{ color: positive ? "#9af0c8" : "#ffb0bb" }}>
              {formatPrice(instrument.price, instrument.decimals)}
            </div>
            <div className="font-mono text-[9px] tabular-nums" style={{ color: positive ? "#5fe6a6" : "#fd7f95" }}>
              {formatSignedPct(instrument.changePct)}
            </div>
          </div>
        </div>

        <div className="mt-2 flex justify-end">
          <Sparkline
            data={instrument.sparkline}
            color={positive ? "#5fe6a6" : "#fd7f95"}
            width={240}
            height={38}
            className="w-full"
          />
        </div>

        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[9px]">
          <Row label="Open" value={formatPrice(instrument.prevClose, instrument.decimals)} />
          <Row label="Volume" value={formatCompact(instrument.volume)} />
          <Row label="High" value={formatPrice(instrument.dayHigh, instrument.decimals)} valueColor="#5fe6a6" />
          <Row label="Low" value={formatPrice(instrument.dayLow, instrument.decimals)} valueColor="#fd7f95" />
        </div>

        <div className="mt-2">
          <div className="flex items-center justify-between font-mono text-[8px] tracking-[0.1em] text-muted/80 uppercase">
            <span>session low</span>
            <span>session high</span>
          </div>
          <div className="relative mt-1 h-[3px] w-full rounded-full bg-gradient-to-r from-rose/40 via-line to-mint/40">
            <span
              className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-void"
              style={{ left: `${position}%`, background: accent, boxShadow: `0 0 8px ${accent}` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-line/30 pb-0.5">
      <span className="tracking-[0.08em] text-muted/80 uppercase">{label}</span>
      <span className="tabular-nums" style={{ color: valueColor ?? "rgba(232,236,245,0.85)" }}>
        {value}
      </span>
    </div>
  );
}
