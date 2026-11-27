import type { MarketKey } from "./market";

export type AgentStatus = "active" | "scanning" | "debating" | "idle" | "risk-hold";

export type InstrumentView = {
  id: number;
  symbol: string;
  name: string;
  market: MarketKey;
  kind: string;
  currency: string;
  unit: string;
  decimals: number;
  price: number;
  prevClose: number;
  dayHigh: number;
  dayLow: number;
  volume: number;
  change: number;
  changePct: number;
  sparkline: number[];
};

export type AgentView = {
  id: number;
  codename: string;
  callsign: string;
  role: string;
  focus: MarketKey | "macro";
  model: string;
  status: AgentStatus;
  accuracy: number;
  pnl: number;
  signalsCount: number;
  latencyMs: number;
  hue: number;
  specialty: string;
  generation: number;
};

export type SignalView = {
  id: number;
  symbol: string;
  market: MarketKey;
  direction: "bullish" | "bearish" | "neutral";
  confidence: number;
  timeframe: string;
  rationale: string;
  entry: number;
  target: number;
  stop: number;
  createdAt: string;
  agentId: number;
  codename: string;
  role: string;
  focus: MarketKey | "macro";
  accuracy: number;
  status: AgentStatus;
};

export type ConsensusView = {
  market: MarketKey;
  label: string;
  bullish: number;
  bearish: number;
  neutral: number;
  count: number;
  score: number;
  bias: "long" | "short" | "neutral";
  leadAgent: string | null;
};

export type AgentStats = {
  total: number;
  active: number;
  scanning: number;
  debating: number;
  idle: number;
  riskHold: number;
  avgAccuracy: number;
  totalSignals: number;
  avgLatency: number;
  byFocus: { focus: string; count: number }[];
  aggregatePnl: number;
};

/** Origin label shown in the UI: database-backed simulation or synthetic demo. */
export type DataOrigin = "database-simulated" | "demo-synthetic";

export type MarketSnapshot = {
  dataOrigin: DataOrigin;
  asOf: string;
  instruments: InstrumentView[];
  sessions: {
    market: MarketKey;
    status: "open" | "closed" | "pre" | "post";
    label: string;
    detail: string;
  }[];
  consensus: ConsensusView[];
  agents: AgentStats;
  signals: SignalView[];
  leaderboard: AgentView[];
};
