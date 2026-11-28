/**
 * Read-only synthetic demo snapshot.
 *
 * Used ONLY when PostgreSQL is unavailable (DATABASE_URL missing or the
 * connection fails). It reuses the same INSTRUMENT_DEFINITIONS and agent
 * generator as the database seeder, so the UI shows the same shapes — but
 * every value is deterministic synthetic data, never claimed as live market
 * data. Nothing here writes to a database or external system.
 */

import { generateAgents, RATIONALE_FRAGMENTS, TIMEFRAMES } from "./agents";
import {
  INSTRUMENT_DEFINITIONS,
  marketSessions,
  MARKETS,
  type MarketKey,
} from "./market";
import type {
  AgentStats,
  AgentView,
  ConsensusView,
  InstrumentView,
  MarketSnapshot,
  SignalView,
} from "./types";

export const DEMO_DATA_ORIGIN = "demo-synthetic" as const;

/** Small deterministic PRNG so repeated builds yield identical demo data. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function instrumentViews(rand: () => number): InstrumentView[] {
  return INSTRUMENT_DEFINITIONS.map((definition, index) => {
    const price = definition.basePrice * (1 + (rand() - 0.5) * 0.004);
    const prevClose = definition.basePrice * (1 + (rand() - 0.52) * 0.006);
    const sparkline: number[] = [];
    let walk = prevClose;
    for (let i = 0; i < 40; i += 1) {
      walk *= 1 + (rand() - 0.5) * 2 * definition.volatility * 2.4;
      sparkline.push(Number(walk.toFixed(definition.decimals + 2)));
    }
    sparkline.push(Number(price.toFixed(definition.decimals + 2)));
    const change = price - prevClose;
    return {
      id: index + 1,
      symbol: definition.symbol,
      name: definition.name,
      market: definition.market,
      kind: definition.kind,
      currency: definition.currency,
      unit: definition.unit,
      decimals: definition.decimals,
      price,
      prevClose,
      dayHigh: Math.max(price, prevClose) * 1.002,
      dayLow: Math.min(price, prevClose) * 0.998,
      volume: Math.round(definition.volumeBase * (0.4 + rand() * 0.6)),
      change,
      changePct: (change / prevClose) * 100,
      sparkline,
    };
  }).sort(
    (a, b) =>
      MARKETS.findIndex((m) => m.key === a.market) -
      MARKETS.findIndex((m) => m.key === b.market),
  );
}

function agentView(index: number, seed: ReturnType<typeof generateAgents>[number]): AgentView {
  return {
    id: index + 1,
    codename: seed.codename,
    callsign: seed.callsign,
    role: seed.role,
    focus: seed.focus,
    model: seed.model,
    status: seed.status,
    accuracy: seed.accuracy,
    pnl: seed.pnl,
    signalsCount: seed.signalsCount,
    latencyMs: seed.latencyMs,
    hue: seed.hue,
    specialty: seed.specialty,
    generation: seed.generation,
  };
}

function agentStats(seeds: ReturnType<typeof generateAgents>): AgentStats {
  const focusCounts = new Map<string, number>();
  let active = 0;
  let scanning = 0;
  let debating = 0;
  let idle = 0;
  let riskHold = 0;
  let accuracy = 0;
  let latency = 0;
  let signals = 0;
  let pnl = 0;
  for (const seed of seeds) {
    focusCounts.set(seed.focus, (focusCounts.get(seed.focus) ?? 0) + 1);
    accuracy += seed.accuracy;
    latency += seed.latencyMs;
    signals += seed.signalsCount;
    pnl += seed.pnl;
    if (seed.status === "active") active += 1;
    else if (seed.status === "scanning") scanning += 1;
    else if (seed.status === "debating") debating += 1;
    else if (seed.status === "idle") idle += 1;
    else riskHold += 1;
  }
  const count = Math.max(1, seeds.length);
  return {
    total: seeds.length,
    active,
    scanning,
    debating,
    idle,
    riskHold,
    avgAccuracy: Number((accuracy / count).toFixed(2)),
    totalSignals: signals,
    avgLatency: Number((latency / count).toFixed(1)),
    byFocus: [...focusCounts.entries()]
      .map(([focus, total]) => ({ focus, count: total }))
      .sort((a, b) => b.count - a.count),
    aggregatePnl: Number(pnl.toFixed(2)),
  };
}

function signalViews(
  seeds: ReturnType<typeof generateAgents>,
  instruments: InstrumentView[],
  rand: () => number,
): SignalView[] {
  const signals: SignalView[] = [];
  for (let i = 0; i < 16; i += 1) {
    const instrument = instruments[i % instruments.length];
    const seed = seeds[(i * 37) % seeds.length];
    const direction = (["bullish", "bearish", "neutral"] as const)[i % 3];
    const rationale = RATIONALE_FRAGMENTS[instrument.market][i % 3];
    signals.push({
      id: i + 1,
      symbol: instrument.symbol,
      market: instrument.market,
      direction,
      confidence: Number((0.52 + rand() * 0.44).toFixed(3)),
      timeframe: TIMEFRAMES[i % TIMEFRAMES.length],
      rationale,
      entry: instrument.price,
      target: Number((instrument.price * (1 + (direction === "bearish" ? -1 : 1) * 0.006)).toFixed(instrument.decimals)),
      stop: Number((instrument.price * (1 + (direction === "bearish" ? 1 : -1) * 0.003)).toFixed(instrument.decimals)),
      createdAt: new Date(Date.now() - i * 120_000).toISOString(),
      agentId: (i % 550) + 1,
      codename: seed.codename,
      role: seed.role,
      focus: seed.focus,
      accuracy: seed.accuracy,
      status: seed.status,
    });
  }
  return signals;
}

function consensus(signals: SignalView[]): ConsensusView[] {
  return MARKETS.map((market) => {
    const subset = signals.filter((signal) => signal.market === market.key);
    const bullish = subset.filter((s) => s.direction === "bullish").length;
    const bearish = subset.filter((s) => s.direction === "bearish").length;
    const neutral = subset.filter((s) => s.direction === "neutral").length;
    const score = subset.length ? (bullish - bearish) / subset.length : 0;
    return {
      market: market.key,
      label: market.label,
      bullish,
      bearish,
      neutral,
      count: subset.length,
      score,
      bias: score > 0.15 ? "long" : score < -0.15 ? "short" : "neutral",
      leadAgent: subset[0]?.codename ?? null,
    };
  });
}

/** Synthetic agent directory rows in the same shape as listAgents(). */
export function buildDemoAgentDirectory(query: {
  q?: string;
  focus?: string;
  status?: string;
  sort?: string;
  page?: number;
  perPage?: number;
}): {
  items: AgentView[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  dataOrigin: typeof DEMO_DATA_ORIGIN;
} {
  const seeds = generateAgents(550).map((seed, index) => agentView(index, seed));
  const term = query.q?.trim().toLowerCase();
  let items = seeds.filter((agent) => {
    if (term && !`${agent.codename} ${agent.callsign} ${agent.role} ${agent.specialty} ${agent.model}`.toLowerCase().includes(term)) return false;
    if (query.focus && query.focus !== "all" && agent.focus !== query.focus) return false;
    if (query.status && query.status !== "all" && agent.status !== query.status) return false;
    return true;
  });
  const sort = query.sort === "pnl" ? "pnl"
    : query.sort === "latency" ? "latencyMs"
    : query.sort === "signals" ? "signalsCount" : "accuracy";
  items = [...items].sort((a, b) => Number(b[sort]) - Number(a[sort]));
  const page = Math.max(1, query.page ?? 1);
  const perPage = Math.min(60, Math.max(6, query.perPage ?? 12));
  const total = items.length;
  return {
    items: items.slice((page - 1) * perPage, page * perPage),
    total,
    page,
    perPage,
    totalPages: Math.max(1, Math.ceil(total / perPage)),
    dataOrigin: DEMO_DATA_ORIGIN,
  };
}

/** Synthetic agent detail in the same shape as getAgentDetail(). */
export function buildDemoAgentDetail(id: number): {
  agent: AgentView;
  signals: SignalView[];
  events: { id: number; kind: string; message: string; createdAt: string }[];
  dataOrigin: typeof DEMO_DATA_ORIGIN;
} | null {
  const seeds = generateAgents(550).map((seed, index) => agentView(index, seed));
  const agent = seeds[id - 1];
  if (!agent) return null;
  const snapshot = buildDemoSnapshot();
  return {
    agent,
    signals: snapshot.signals.filter((s) => s.agentId === id).slice(0, 6),
    events: [],
    dataOrigin: DEMO_DATA_ORIGIN,
  };
}

export function buildDemoSnapshot(now: Date = new Date()): MarketSnapshot {
  const rand = mulberry32(20261127);
  const seeds = generateAgents(550);
  const instruments = instrumentViews(rand);
  const signals = signalViews(seeds, instruments, rand);
  const leaderboard = [...seeds]
    .sort((a, b) => b.accuracy - a.accuracy)
    .slice(0, 6)
    .map((seed, index) => agentView(index, seed));

  return {
    dataOrigin: DEMO_DATA_ORIGIN,
    asOf: now.toISOString(),
    instruments,
    sessions: marketSessions(now),
    consensus: consensus(signals),
    agents: agentStats(seeds),
    signals,
    leaderboard,
  };
}
