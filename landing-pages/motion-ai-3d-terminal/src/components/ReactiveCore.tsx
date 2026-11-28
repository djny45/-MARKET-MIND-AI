"use client";

import { useMemo } from "react";
import { Scene } from "@/components/Scene";
import { Chip } from "@/components/ui";
import {
  FOCUS_COLOR,
  formatSignedPct,
  focusLabel,
} from "@/lib/ui";
import { MARKETS, formatPrice, type MarketKey } from "@/lib/market";
import type { AgentStats, ConsensusView, InstrumentView, SignalView } from "@/lib/types";
import { deriveSceneTelemetry } from "@/lib/scene";

/**
 * The single reactive 3D element of the terminal.
 *
 * There is exactly one WebGL/canvas surface on the page: the registered
 * ThreeUI `ConstellationField` (`gateway-flow`) rendered by <Scene />. Nothing
 * else draws. All 550 agents feed this one scene through aggregated telemetry:
 *
 *   speed     ← share of agents actively working the tape
 *   opacity   ← signal velocity across the swarm
 *   tint      ← selected desk colour (CSS `color` blend over the shader)
 *   density   ← pinned to the configured 1.00 (rebuilding the scene is costly)
 */
export function ReactiveCore({
  instrument,
  stats,
  consensus,
  signals,
  selectedMarket,
  onMarketChange,
  onScan,
  scanning,
  autoScan,
  onToggleAutoScan,
  demoMode = false,
}: {
  instrument: InstrumentView | undefined;
  stats: AgentStats;
  consensus: ConsensusView[];
  signals: SignalView[];
  selectedMarket: MarketKey;
  onMarketChange: (market: MarketKey) => void;
  onScan: () => void;
  scanning: boolean;
  autoScan: boolean;
  onToggleAutoScan: () => void;
  demoMode?: boolean;
}) {
  const accent = FOCUS_COLOR[selectedMarket] ?? "#f6c76b";

  // ---- swarm → scene telemetry -------------------------------------------
  const { working, activity, energy, speed, opacity } = deriveSceneTelemetry(stats, signals.length);

  // Stable, memoised lattice of all 550 agents (grouped per desk).
  const lattice = useMemo(() => {
    const groups = stats.byFocus.filter((row) => row.count > 0);
    const cells: { key: string; color: string; focus: string }[] = [];
    groups.forEach((group) => {
      const color = FOCUS_COLOR[group.focus] ?? "#8a90ac";
      for (let i = 0; i < group.count; i += 1) {
        cells.push({ key: `${group.focus}-${i}`, color, focus: group.focus });
      }
    });
    return cells;
  }, [stats.byFocus]);

  const visibleLattice = lattice.slice(0, 550);
  const consensusView = consensus.find((item) => item.market === selectedMarket);
  const biasColor =
    consensusView?.bias === "long" ? "#5fe6a6" : consensusView?.bias === "short" ? "#fd7f95" : "#f6c76b";

  return (
    <div className="panel panel-iris relative overflow-hidden rounded-xl">
      <div className="relative h-[420px] w-full bg-black sm:h-[500px]">
        {/* ── the one and only 3D surface ───────────────────────────────── */}
        <Scene speed={speed} opacity={opacity} />

        {/* colour combination: hue/saturation blend over the shader */}
        <div
          className="pointer-events-none absolute inset-0 transition-all duration-700"
          style={{
            background: `linear-gradient(118deg, #a78bfa 0%, #8b7bf0 38%, ${accent} 100%)`,
            mixBlendMode: "color",
            opacity: 0.88,
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 transition-opacity duration-700"
          style={{
            background: `radial-gradient(ellipse 62% 62% at 50% 52%, ${accent}3d, transparent 72%)`,
            mixBlendMode: "screen",
            opacity: 0.55 + energy * 0.35,
          }}
        />

        {/* ── HUD: top ─────────────────────────────────────────────────── */}
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-3.5">
          <div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-aqua opacity-70" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-aqua" />
              </span>
              <span className="font-mono text-[9.5px] tracking-[0.22em] text-aqua uppercase">
                reactive 3d · gateway flow
              </span>
            </div>
            <p className="mt-1 font-mono text-[9px] tracking-[0.15em] text-muted uppercase">
              {stats.total.toLocaleString()} generated profiles driving one shader
              <span className="text-iris"> · {Math.round(energy * 100)}% energy</span>
            </p>
          </div>
          <div className="pointer-events-auto flex flex-wrap justify-end gap-1">
            {MARKETS.map((market) => (
              <Chip
                key={market.key}
                active={selectedMarket === market.key}
                color={FOCUS_COLOR[market.key]}
                onClick={() => onMarketChange(market.key)}
              >
                {market.short}
              </Chip>
            ))}
          </div>
        </div>

        {/* corner brackets */}
        <span className="pointer-events-none absolute top-3 left-3 h-4 w-4 border-t border-l border-iris/40" />
        <span className="pointer-events-none absolute top-3 right-3 h-4 w-4 border-t border-r border-iris/40" />
        <span className="pointer-events-none absolute bottom-3 left-3 h-4 w-4 border-b border-l border-iris/40" />
        <span className="pointer-events-none absolute right-3 bottom-3 h-4 w-4 border-r border-b border-iris/40" />

        {/* ── price readout ────────────────────────────────────────────── */}
        <div className="pointer-events-none absolute top-[52px] right-3.5 text-right">
          <div className="font-mono text-[8px] tracking-[0.16em] text-muted/80 uppercase">
            {instrument?.symbol ?? "—"} · {focusLabel(selectedMarket)} desk
          </div>
          <div className="font-mono text-[19px] font-semibold tabular-nums text-iris-bright text-glow-iris">
            {instrument ? formatPrice(instrument.price, instrument.decimals) : "—"}
          </div>
          <div className="font-mono text-[9px] tabular-nums" style={{ color: (instrument?.changePct ?? 0) >= 0 ? "#5fe6a6" : "#fd7f95" }}>
            {instrument ? formatSignedPct(instrument.changePct) : "—"}
            <span className="ml-2 text-muted">{consensusView?.bias.toUpperCase() ?? "NEUTRAL"}</span>
          </div>
        </div>

        {/* ── agent lattice: every one of the 550, tinted per desk ──────── */}
        <div className="pointer-events-none absolute inset-x-3.5 bottom-[74px]">
          <div className="mb-1 flex items-center justify-between font-mono text-[8px] tracking-[0.14em] text-muted/80 uppercase">
            <span>agent lattice · {visibleLattice.length} generated profiles</span>
            <span className="text-aqua/80">desk tinted</span>
          </div>
          <div
            className="grid gap-[2px]"
            style={{ gridTemplateColumns: "repeat(auto-fill, minmax(3px, 1fr))" }}
            aria-hidden="true"
          >
            {visibleLattice.map((cell, index) => (
              <span
                key={cell.key}
                className="h-[3px] w-full rounded-[1px]"
                style={{
                  background: cell.color,
                  opacity: 0.24 + ((index * 37) % 11) / 16 + activity * 0.35,
                  boxShadow: index % 23 === 0 ? `0 0 5px ${cell.color}` : undefined,
                }}
              />
            ))}
          </div>
        </div>

        {/* ── HUD: bottom bar ──────────────────────────────────────────── */}
        <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 bg-void/70 px-3.5 py-2 backdrop-blur-md">
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1">
            <Metric label="speed" value={`${speed.toFixed(2)}×`} color="#a78bfa" />
            <Metric label="profiles" value={stats.total.toLocaleString()} color="#f6c76b" />
            <Metric label="working" value={working.toString()} color="#5fe6a6" />
            <Metric label="debating" value={stats.debating.toString()} color="#c4b5fd" />
            <Metric label="signals" value={signals.length.toString()} color="#4fe6d8" />
            <Metric label="acc" value={`${stats.avgAccuracy.toFixed(1)}%`} color="#7fa6ff" />
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={onToggleAutoScan}
              className="rounded-sm border px-1.5 py-1 font-mono text-[9px] tracking-[0.12em] uppercase transition-colors"
              style={{
                color: autoScan ? "#5fe6a6" : "#8a90ac",
                borderColor: autoScan ? "rgba(95,230,166,0.5)" : "rgba(49,58,99,0.8)",
                background: autoScan ? "rgba(95,230,166,0.1)" : "transparent",
              }}
            >
              auto {autoScan ? "on" : "off"}
            </button>
            <button
              type="button"
              onClick={onScan}
              disabled={scanning}
              className="rounded-sm border border-iris/50 bg-iris/10 px-2 py-1 font-mono text-[9px] tracking-[0.12em] text-iris uppercase transition-colors hover:bg-iris/20 disabled:opacity-50"
            >
              {scanning ? "scanning…" : demoMode ? "simulate scan" : "run scan"}
            </button>
          </div>
        </div>

        {/* side rail */}
        <div className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 space-y-1">
          {["550-AGENT MESH", "REACTIVE SHADER", "ONE SURFACE"].map((label, index) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full" style={{ background: accent, opacity: 1 - index * 0.28 }} />
              <span className="font-mono text-[8px] tracking-[0.18em] text-muted/80">{label}</span>
            </div>
          ))}
        </div>

        <div className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-right">
          <div className="font-mono text-[8px] tracking-[0.18em] text-muted/80">BIAS</div>
          <div className="font-mono text-[10px]" style={{ color: biasColor }}>
            {consensusView?.score !== undefined ? `${consensusView.score > 0 ? "+" : ""}${consensusView.score}` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-baseline gap-1">
      <span className="font-mono text-[8px] tracking-[0.14em] text-muted uppercase">{label}</span>
      <span className="font-mono text-[11px] tabular-nums" style={{ color }}>
        {value}
      </span>
    </div>
  );
}
