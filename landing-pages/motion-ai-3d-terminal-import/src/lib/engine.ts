import { and, desc, eq, gte, ilike, inArray, or, sql } from "drizzle-orm";
import { db } from "@/db";
import { agentEvents, agents, candles, instruments, signals } from "@/db/schema";
import { generateAgents, RATIONALE_FRAGMENTS, TIMEFRAMES } from "./agents";
import {
  INSTRUMENT_DEFINITIONS,
  isMarketKey,
  marketSessions,
  MARKETS,
  type MarketKey,
} from "./market";
import type {
  AgentStats,
  AgentStatus,
  AgentView,
  ConsensusView,
  InstrumentView,
  MarketSnapshot,
  SignalView,
} from "./types";

const globalForEngine = globalThis as typeof globalThis & {
  __synodSeedPromise?: Promise<void>;
  __synodLastAdvance?: number;
  __synodLastCandle?: number;
  __synodLastPrune?: number;
};

const AGENT_STATUSES: AgentStatus[] = ["active", "scanning", "debating", "idle", "risk-hold"];

function gauss(): number {
  let u = 0;
  let v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function toAgentStatus(value: string): AgentStatus {
  return (AGENT_STATUSES as string[]).includes(value) ? (value as AgentStatus) : "active";
}

function toFocus(value: string): MarketKey | "macro" {
  return isMarketKey(value) ? value : "macro";
}

type AgentRow = typeof agents.$inferSelect;
type InstrumentRow = typeof instruments.$inferSelect;

function toAgentView(row: AgentRow): AgentView {
  return {
    id: row.id,
    codename: row.codename,
    callsign: row.callsign,
    role: row.role,
    focus: toFocus(row.focus),
    model: row.model,
    status: toAgentStatus(row.status),
    accuracy: row.accuracy,
    pnl: row.pnl,
    signalsCount: row.signalsCount,
    latencyMs: row.latencyMs,
    hue: row.hue,
    specialty: row.specialty,
    generation: row.generation,
  };
}

const EMPTY_STATS: AgentStats = {
  total: 0,
  active: 0,
  scanning: 0,
  debating: 0,
  idle: 0,
  riskHold: 0,
  avgAccuracy: 0,
  totalSignals: 0,
  avgLatency: 0,
  byFocus: [],
  aggregatePnl: 0,
};

async function seedDatabase(): Promise<void> {
  const [instrumentCount] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(instruments);

  if (instrumentCount.count === 0) {
    const now = Date.now();
    const values = INSTRUMENT_DEFINITIONS.map((definition, index) => {
      const random = mulberry32(41 + index * 7)();
      const open = definition.basePrice * (1 + (random - 0.5) * 0.004);
      return {
        symbol: definition.symbol,
        name: definition.name,
        market: definition.market,
        kind: definition.kind,
        currency: definition.currency,
        unit: definition.unit,
        decimals: definition.decimals,
        price: open,
        prevClose: definition.basePrice * (1 + (random - 0.52) * 0.006),
        dayOpen: open,
        dayHigh: open * 1.002,
        dayLow: open * 0.998,
        volume: Math.round(definition.volumeBase * (0.4 + random * 0.6)),
        volatility: definition.volatility,
        updatedAt: new Date(now),
      };
    });
    await db.insert(instruments).values(values).onConflictDoNothing();
  }

  const instrumentRows = await db.select().from(instruments);
  const [candleCount] = await db.select({ count: sql<number>`count(*)::int` }).from(candles);

  if (candleCount.count === 0) {
    const candleRows: { instrumentId: number; price: number; volume: number; ts: Date }[] = [];
    for (const row of instrumentRows) {
      const rand = mulberry32(row.id * 977 + 13);
      let price = row.price * (1 - (0.002 + rand() * 0.008));
      const points: number[] = [];
      for (let i = 0; i < 72; i += 1) {
        const shock = (rand() - 0.5) * 2 * row.volatility * 1.9;
        price *= 1 + shock;
        points.push(price);
      }
      const scale = row.price / (points[points.length - 1] ?? row.price);
      points.forEach((point, index) => {
        candleRows.push({
          instrumentId: row.id,
          price: Number((point * scale).toFixed(6)),
          volume: Math.round(400 + rand() * 2_400),
          ts: new Date(Date.now() - (points.length - index) * 60_000),
        });
      });
      await db
        .update(instruments)
        .set({
          dayOpen: Number(points[0].toFixed(6)),
          dayHigh: Number((Math.max(...points) * scale).toFixed(6)),
          dayLow: Number((Math.min(...points) * scale).toFixed(6)),
        })
        .where(eq(instruments.id, row.id));
    }
    if (candleRows.length > 0) {
      await db.insert(candles).values(candleRows);
    }
  }

  const [agentCount] = await db.select({ count: sql<number>`count(*)::int` }).from(agents);
  if (agentCount.count < 550) {
    const seeds = generateAgents(550);
    const chunkSize = 110;
    for (let i = 0; i < seeds.length; i += chunkSize) {
      await db
        .insert(agents)
        .values(seeds.slice(i, i + chunkSize))
        .onConflictDoNothing();
    }
  }

  const [signalCount] = await db.select({ count: sql<number>`count(*)::int` }).from(signals);
  if (signalCount.count < 12) {
    for (const market of ["gold", "forex", "us", "india"] as MarketKey[]) {
      await createSignals(4, market);
    }
  }
}

export async function ensureSeeded(): Promise<void> {
  if (!globalForEngine.__synodSeedPromise) {
    globalForEngine.__synodSeedPromise = seedDatabase().catch((error) => {
      globalForEngine.__synodSeedPromise = undefined;
      throw error;
    });
  }
  await globalForEngine.__synodSeedPromise;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export async function advanceMarket(): Promise<void> {
  await ensureSeeded();
  const now = Date.now();
  const last = globalForEngine.__synodLastAdvance ?? 0;
  if (now - last < 900) return;
  globalForEngine.__synodLastAdvance = now;

  const rows = await db.select().from(instruments);
  const pulse = gauss() * 0.00052;
  const updates = rows.map((row) => {
    const elapsedSeconds = Math.max(0.6, Math.min(20, (now - row.updatedAt.getTime()) / 1000));
    const step = Math.sqrt(elapsedSeconds / 3);
    const marketSensitivity = row.market === "us" || row.market === "india" ? 1 : row.market === "forex" ? 0.35 : -0.45;
    const shock = gauss() * row.volatility * step + pulse * marketSensitivity;
    const reversion = ((row.prevClose - row.price) / row.price) * 0.018 * step;
    const nextPrice = Math.max(row.price * 0.5, row.price * (1 + shock + reversion));
    const nextVolume = row.volume + Math.round(200 + Math.random() * 4_200);
    return db
      .update(instruments)
      .set({
        price: nextPrice,
        dayHigh: Math.max(row.dayHigh, nextPrice),
        dayLow: Math.min(row.dayLow, nextPrice),
        volume: nextVolume,
        updatedAt: new Date(now),
      })
      .where(eq(instruments.id, row.id));
  });

  await Promise.all(updates);

  const lastCandle = globalForEngine.__synodLastCandle ?? 0;
  if (now - lastCandle > 15_000) {
    globalForEngine.__synodLastCandle = now;
    const fresh = await db.select().from(instruments);
    await db.insert(candles).values(
      fresh.map((row) => ({
        instrumentId: row.id,
        price: row.price,
        volume: Math.round(200 + Math.random() * 2_000),
        ts: new Date(now),
      })),
    );
  }

  await db.execute(sql`
    update agents set
      status = (array['active','active','active','scanning','scanning','debating','idle','risk-hold'])[floor(random() * 8) + 1],
      latency_ms = greatest(22, least(520, latency_ms + floor(random() * 61) - 30)),
      pnl = round((pnl + (random() - 0.46) * 4.2)::numeric, 2),
      signals_count = signals_count + floor(random() * 3)::int
    where id in (select id from agents order by random() limit 10)
  `);

  await db.execute(sql`
    insert into agent_events (agent_id, kind, message)
    select id,
      (array['scan','risk','signal','consensus','execution'])[floor(random() * 5) + 1],
      (array[
        'Re-derived liquidity map across the last 3 sessions',
        'Risk envelope validated — drawdown budget intact',
        'Cross-checked signal against sibling agent consensus',
        'Order-book imbalance detected on the 5-minute tape',
        'Rebalanced agent weight after walk-forward audit',
        'Escalated a divergence to the desk supervisor',
        'Refreshed macro factor loadings from the latest print'
      ])[floor(random() * 7) + 1]
    from agents order by random() limit 3
  `);

  const lastPrune = globalForEngine.__synodLastPrune ?? 0;
  if (now - lastPrune > 60_000) {
    globalForEngine.__synodLastPrune = now;
    await db.execute(sql`delete from candles where ts < now() - interval '6 hours'`);
    await db.execute(sql`delete from signals where created_at < now() - interval '12 hours'`);
    await db.execute(sql`delete from agent_events where created_at < now() - interval '3 hours'`);
  }
}

type SignalJoinRow = {
  signal: typeof signals.$inferSelect;
  agent: AgentRow;
};

function toSignalView(row: SignalJoinRow): SignalView {
  const market = isMarketKey(row.signal.market) ? row.signal.market : "gold";
  return {
    id: row.signal.id,
    symbol: row.signal.symbol,
    market,
    direction: row.signal.direction as SignalView["direction"],
    confidence: row.signal.confidence,
    timeframe: row.signal.timeframe,
    rationale: row.signal.rationale,
    entry: row.signal.entry,
    target: row.signal.target,
    stop: row.signal.stop,
    createdAt: row.signal.createdAt.toISOString(),
    agentId: row.agent.id,
    codename: row.agent.codename,
    role: row.agent.role,
    focus: toFocus(row.agent.focus),
    accuracy: row.agent.accuracy,
    status: toAgentStatus(row.agent.status),
  };
}

export async function getRecentSignals(limit = 16): Promise<SignalView[]> {
  const rows = await db
    .select({ signal: signals, agent: agents })
    .from(signals)
    .innerJoin(agents, eq(signals.agentId, agents.id))
    .orderBy(desc(signals.createdAt))
    .limit(limit);
  return rows.map(toSignalView);
}

async function createSignals(count: number, marketFilter?: MarketKey): Promise<SignalView[]> {
  const statusFilter = inArray(agents.status, ["active", "scanning", "debating"]);
  const rows = await db
    .select()
    .from(agents)
    .where(
      marketFilter
        ? and(statusFilter, or(eq(agents.focus, marketFilter), eq(agents.focus, "macro")))
        : statusFilter,
    )
    .orderBy(sql`random()`)
    .limit(count);
  if (rows.length === 0) return [];

  const instrumentRows = await db.select().from(instruments);
  const byMarket = new Map<string, InstrumentRow[]>();
  for (const row of instrumentRows) {
    const list = byMarket.get(row.market) ?? [];
    list.push(row);
    byMarket.set(row.market, list);
  }

  const created: SignalView[] = [];

  for (const agent of rows) {
    const focus = marketFilter ?? toFocus(agent.focus);
    const marketPool =
      focus === "macro" ? instrumentRows : (byMarket.get(focus) ?? instrumentRows);
    const instrument = marketPool[Math.floor(Math.random() * marketPool.length)];
    if (!instrument) continue;

    const changePct = ((instrument.price - instrument.prevClose) / instrument.prevClose) * 100;
    const roll = Math.random();
    const bullishBias = changePct > 0 ? 0.12 : -0.12;
    const direction: SignalView["direction"] =
      roll < 0.45 + bullishBias ? "bullish" : roll < 0.82 + bullishBias ? "bearish" : "neutral";
    const confidence = Math.min(98, 52 + Math.round(Math.random() * 44));
    const timeframe = TIMEFRAMES[Math.floor(Math.random() * TIMEFRAMES.length)];
    const marketKey = isMarketKey(instrument.market) ? instrument.market : focus;
    const pool = RATIONALE_FRAGMENTS[focus === "macro" ? "macro" : marketKey];
    const rationale = `${pool[Math.floor(Math.random() * pool.length)]} Focus: ${agent.specialty}.`;
    const spread = 0.0016 + Math.random() * 0.0035;
    const sign = direction === "bearish" ? -1 : direction === "neutral" ? 0 : 1;
    const entry = instrument.price;
    const target = entry * (1 + sign * spread);
    const stop = entry * (1 - sign * spread * 0.55);

    const [inserted] = await db
      .insert(signals)
      .values({
        agentId: agent.id,
        symbol: instrument.symbol,
        market: marketKey,
        direction,
        confidence,
        timeframe,
        rationale,
        entry: Number(entry.toFixed(6)),
        target: Number(target.toFixed(6)),
        stop: Number(stop.toFixed(6)),
      })
      .returning();

    await db
      .update(agents)
      .set({ signalsCount: agent.signalsCount + 1, status: Math.random() > 0.7 ? "scanning" : "active" })
      .where(eq(agents.id, agent.id));

    await db.insert(agentEvents).values({
      agentId: agent.id,
      kind: "signal",
      message: `Published ${direction.toUpperCase()} on ${instrument.symbol} @ ${confidence}% confidence`,
    });

    created.push(
      toSignalView({
        signal: inserted,
        agent: { ...agent, signalsCount: agent.signalsCount + 1 },
      }),
    );
  }

  return created;
}

export async function generateSignals(count: number): Promise<SignalView[]> {
  await ensureSeeded();
  return createSignals(count);
}

function buildConsensus(recent: SignalView[]): ConsensusView[] {
  return MARKETS.map((market) => {
    const relevant = recent.filter((signal) => signal.market === market.key);
    let bullish = 0;
    let bearish = 0;
    let neutral = 0;
    let weighted = 0;
    let lead: SignalView | null = null;

    for (const signal of relevant) {
      const weight = (signal.confidence / 100) * (0.6 + signal.accuracy / 100);
      weighted += signal.direction === "bearish" ? -weight : signal.direction === "neutral" ? 0 : weight;
      if (signal.direction === "bullish") bullish += 1;
      else if (signal.direction === "bearish") bearish += 1;
      else neutral += 1;
      if (!lead || signal.confidence > lead.confidence) lead = signal;
    }

    const score = relevant.length === 0 ? 0 : Math.max(-100, Math.min(100, (weighted / relevant.length) * 100));
    const bias: ConsensusView["bias"] = score > 10 ? "long" : score < -10 ? "short" : "neutral";

    return {
      market: market.key,
      label: market.label,
      bullish,
      bearish,
      neutral,
      count: relevant.length,
      score: Math.round(score),
      bias,
      leadAgent: lead && bias !== "neutral" ? lead.codename : lead?.codename ?? null,
    } satisfies ConsensusView;
  });
}

async function getAgentStats(): Promise<AgentStats> {
  const [row] = await db
    .select({
      total: sql<number>`count(*)::int`,
      active: sql<number>`count(*) filter (where status = 'active')::int`,
      scanning: sql<number>`count(*) filter (where status = 'scanning')::int`,
      debating: sql<number>`count(*) filter (where status = 'debating')::int`,
      idle: sql<number>`count(*) filter (where status = 'idle')::int`,
      riskHold: sql<number>`count(*) filter (where status = 'risk-hold')::int`,
      avgAccuracy: sql<number>`coalesce(avg(accuracy), 0)::float`,
      totalSignals: sql<number>`coalesce(sum(signals_count), 0)::int`,
      avgLatency: sql<number>`coalesce(avg(latency_ms), 0)::float`,
      aggregatePnl: sql<number>`coalesce(sum(pnl), 0)::float`,
    })
    .from(agents);

  const focusRows = await db
    .select({ focus: agents.focus, count: sql<number>`count(*)::int` })
    .from(agents)
    .groupBy(agents.focus);

  if (!row) return EMPTY_STATS;
  return { ...row, byFocus: focusRows };
}

export async function getSnapshot(): Promise<MarketSnapshot> {
  await advanceMarket();

  const [instrumentRows, candleRows, agentStats, initialSignals, leaderboardRows] = await Promise.all([
    db.select().from(instruments),
    db
      .select({
        instrumentId: candles.instrumentId,
        price: candles.price,
        ts: candles.ts,
      })
      .from(candles)
      .where(gte(candles.ts, new Date(Date.now() - 3 * 60 * 60 * 1000)))
      .orderBy(desc(candles.ts))
      .limit(1_200),
    getAgentStats(),
    getRecentSignals(220),
    db.select().from(agents).orderBy(desc(agents.accuracy)).limit(6),
  ]);

  let recentSignals = initialSignals;
  const uncovered = MARKETS.map((market) => market.key).filter(
    (market) => !recentSignals.some((signal) => signal.market === market),
  );
  if (uncovered.length > 0) {
    for (const market of uncovered) {
      await createSignals(3, market);
    }
    recentSignals = await getRecentSignals(220);
  }

  const sparkByInstrument = new Map<number, number[]>();
  for (const candle of candleRows) {
    const list = sparkByInstrument.get(candle.instrumentId) ?? [];
    if (list.length < 56) list.push(candle.price);
    sparkByInstrument.set(candle.instrumentId, list);
  }

  const instrumentViews: InstrumentView[] = instrumentRows
    .map((row) => {
      const change = row.price - row.prevClose;
      const spark = (sparkByInstrument.get(row.id) ?? []).slice().reverse();
      return {
        id: row.id,
        symbol: row.symbol,
        name: row.name,
        market: (isMarketKey(row.market) ? row.market : "gold") as MarketKey,
        kind: row.kind,
        currency: row.currency,
        unit: row.unit,
        decimals: row.decimals,
        price: row.price,
        prevClose: row.prevClose,
        dayHigh: row.dayHigh,
        dayLow: row.dayLow,
        volume: row.volume,
        change,
        changePct: (change / row.prevClose) * 100,
        sparkline: spark.length > 1 ? [...spark, row.price] : [row.prevClose, row.price],
      };
    })
    .sort(
      (a, b) =>
        MARKETS.findIndex((market) => market.key === a.market) -
        MARKETS.findIndex((market) => market.key === b.market),
    );

  return {
    asOf: new Date().toISOString(),
    instruments: instrumentViews,
    sessions: marketSessions(),
    consensus: buildConsensus(recentSignals),
    agents: agentStats,
    signals: recentSignals.slice(0, 14),
    leaderboard: leaderboardRows.map(toAgentView),
  };
}

export type AgentQuery = {
  q?: string;
  focus?: string;
  status?: string;
  sort?: string;
  page?: number;
  perPage?: number;
};

export async function listAgents(query: AgentQuery): Promise<{
  items: AgentView[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}> {
  await ensureSeeded();
  const page = Math.max(1, query.page ?? 1);
  const perPage = Math.min(60, Math.max(6, query.perPage ?? 12));

  const filters = [];
  if (query.q && query.q.trim().length > 0) {
    const term = `%${query.q.trim()}%`;
    filters.push(
      or(
        ilike(agents.codename, term),
        ilike(agents.callsign, term),
        ilike(agents.role, term),
        ilike(agents.specialty, term),
        ilike(agents.model, term),
      ),
    );
  }
  if (query.focus && query.focus !== "all" && isMarketKey(query.focus)) {
    filters.push(eq(agents.focus, query.focus));
  }
  if (query.focus === "macro") filters.push(eq(agents.focus, "macro"));
  if (query.status && query.status !== "all" && (AGENT_STATUSES as string[]).includes(query.status)) {
    filters.push(eq(agents.status, query.status));
  }

  const where = filters.length > 0 ? and(...filters) : undefined;

  const order =
    query.sort === "pnl"
      ? desc(agents.pnl)
      : query.sort === "latency"
        ? agents.latencyMs
        : query.sort === "signals"
          ? desc(agents.signalsCount)
          : desc(agents.accuracy);

  const [items, countRows] = await Promise.all([
    db
      .select()
      .from(agents)
      .where(where)
      .orderBy(order)
      .limit(perPage)
      .offset((page - 1) * perPage),
    db.select({ count: sql<number>`count(*)::int` }).from(agents).where(where),
  ]);

  const total = countRows[0]?.count ?? 0;
  return {
    items: items.map(toAgentView),
    total,
    page,
    perPage,
    totalPages: Math.max(1, Math.ceil(total / perPage)),
  };
}

export async function getAgentDetail(id: number): Promise<{
  agent: AgentView;
  signals: SignalView[];
  events: { id: number; kind: string; message: string; createdAt: string }[];
} | null> {
  const [row] = await db.select().from(agents).where(eq(agents.id, id)).limit(1);
  if (!row) return null;

  const [signalRows, eventRows] = await Promise.all([
    db
      .select({ signal: signals, agent: agents })
      .from(signals)
      .innerJoin(agents, eq(signals.agentId, agents.id))
      .where(eq(signals.agentId, id))
      .orderBy(desc(signals.createdAt))
      .limit(6),
    db
      .select()
      .from(agentEvents)
      .where(eq(agentEvents.agentId, id))
      .orderBy(desc(agentEvents.createdAt))
      .limit(6),
  ]);

  return {
    agent: toAgentView(row),
    signals: signalRows.map(toSignalView),
    events: eventRows.map((event) => ({
      id: event.id,
      kind: event.kind,
      message: event.message,
      createdAt: event.createdAt.toISOString(),
    })),
  };
}

export async function runSwarmScan(count = 4): Promise<{ signals: SignalView[]; consensus: ConsensusView[] }> {
  await advanceMarket();
  const created = await generateSignals(Math.min(10, Math.max(1, count)));
  const recent = await getRecentSignals(220);
  return { signals: created, consensus: buildConsensus(recent) };
}
