import type { AgentStatus } from "./types";
import type { MarketKey } from "./market";

export const AGENT_COUNT = 550;

export type AgentSeed = {
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

export const ROLES: { name: string; specialty: string[] }[] = [
  {
    name: "Macro Strategist",
    specialty: ["rate differentials", "central-bank path", "yield-curve regime", "liquidity cycle"],
  },
  {
    name: "Order-Flow Sniper",
    specialty: ["footprint clusters", "sweep detection", "iceberg tracking", "tape imbalance"],
  },
  {
    name: "Quant Analyst",
    specialty: ["cointegration alpha", "momentum factor", "vol carry", "mean-reversion band"],
  },
  {
    name: "Sentiment Reader",
    specialty: ["news entropy", "social skew", "positioning crowd", "headline velocity"],
  },
  {
    name: "Risk Warden",
    specialty: ["drawdown guard", "beta exposure", "gap-risk hedge", "tail sizing"],
  },
  {
    name: "Pattern Cartographer",
    specialty: ["harmonic lattice", "volume-profile nodes", "market-structure shift", "wyckoff phase"],
  },
  {
    name: "Liquidity Hunter",
    specialty: ["dark-pool prints", "depth refill", "stop-liquidity map", "auction repair"],
  },
  {
    name: "News Arbitrageur",
    specialty: ["RBI headline desk", "FOMC whisper", "geopolitical shock", "earnings drift"],
  },
  {
    name: "Backtest Auditor",
    specialty: ["walk-forward proof", "overfit shield", "regime splits", "transaction cost model"],
  },
  {
    name: "Volatility Architect",
    specialty: ["IV surface skew", "gamma pin", "vanna flows", "vol-of-vol"],
  },
  {
    name: "Execution Router",
    specialty: ["TWAP slicing", "maker rebate", "slippage guard", "venue scoring"],
  },
  {
    name: "Options Flow Analyst",
    specialty: ["0DTE sweep", "dealer gamma", "unusual OI", "risk-reversal skew"],
  },
];

const FOCUS_WEIGHTS: { focus: MarketKey | "macro"; weight: number }[] = [
  { focus: "gold", weight: 120 },
  { focus: "forex", weight: 130 },
  { focus: "us", weight: 140 },
  { focus: "india", weight: 130 },
  { focus: "macro", weight: 30 },
];

const MODELS = [
  "Aurum-4o",
  "Synod-70B",
  "Kavach-13B",
  "BullionNet-v3",
  "FX-Transformer",
  "Nifty-RL-9",
  "DeepTape-2",
  "MacroReasoner",
  "FlowFormer",
  "RiskGuard-7B",
  "SigmaCore-XL",
  "Ledger-LLM",
];

const CODENAME_ROOTS = [
  "ORACLE",
  "SENTINEL",
  "VECTOR",
  "AURUM",
  "KRAKEN",
  "PULSAR",
  "NEXUS",
  "CIPHER",
  "HELIOS",
  "TITAN",
  "OMEN",
  "QUANTA",
  "SPECTRE",
  "ATLAS",
  "VORTEX",
  "ZENITH",
  "RAPTOR",
  "MONSOON",
  "MANDALA",
  "SUTRA",
  "KAIZEN",
  "ARGUS",
  "NOVA",
  "ONYX",
];

const CALLSIGN_A = [
  "Arjun",
  "Meera",
  "Kabir",
  "Anaya",
  "Rohan",
  "Isha",
  "Dev",
  "Tara",
  "Neel",
  "Sana",
  "Adrian",
  "Naomi",
  "Felix",
  "Iris",
  "Marcus",
  "Lena",
  "Yuki",
  "Omar",
  "Priya",
  "Ethan",
  "Zara",
  "Kiran",
  "Nadia",
  "Theo",
];

const CALLSIGN_B = [
  "Rao",
  "Kapoor",
  "Mehta",
  "Iyer",
  "Sharma",
  "Nair",
  "Bose",
  "Vance",
  "Cole",
  "Hale",
  "Okafor",
  "Ito",
  "Khan",
  "Silva",
  "Reyes",
  "Volkov",
  "Fischer",
  "Dube",
  "Chandra",
  "Menon",
  "Walsh",
  "Park",
  "Bauer",
  "Rathore",
];

const STATUSES: AgentStatus[] = ["active", "active", "active", "scanning", "scanning", "debating", "idle", "risk-hold"];

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

export function generateAgents(count = AGENT_COUNT): AgentSeed[] {
  const rand = mulberry32(918_273);
  const focusPool: (MarketKey | "macro")[] = [];
  for (const item of FOCUS_WEIGHTS) {
    for (let i = 0; i < item.weight; i += 1) focusPool.push(item.focus);
  }

  const agents: AgentSeed[] = [];

  for (let index = 0; index < count; index += 1) {
    const focus = focusPool[index % focusPool.length];
    const role = ROLES[Math.floor(rand() * ROLES.length)];
    const root = CODENAME_ROOTS[Math.floor(rand() * CODENAME_ROOTS.length)];
    const codename = `${root}-${1000 + index}`;
    const callsign = `${CALLSIGN_A[Math.floor(rand() * CALLSIGN_A.length)]} ${CALLSIGN_B[Math.floor(rand() * CALLSIGN_B.length)]}`;
    const specialty = role.specialty[Math.floor(rand() * role.specialty.length)];
    const baseAccuracy = 58 + rand() * 36;
    const status = STATUSES[Math.floor(rand() * STATUSES.length)];

    agents.push({
      codename,
      callsign,
      role: role.name,
      focus,
      model: MODELS[Math.floor(rand() * MODELS.length)],
      status,
      accuracy: Math.round(baseAccuracy * 10) / 10,
      pnl: Math.round((rand() * 2 - 0.55) * 48_000) / 100,
      signalsCount: 40 + Math.floor(rand() * 9_800),
      latencyMs: 38 + Math.floor(rand() * 340),
      hue: Math.floor(36 + rand() * 24),
      specialty,
      generation: 1 + Math.floor(rand() * 4),
    });
  }

  return agents;
}

export const RATIONALE_FRAGMENTS: Record<MarketKey | "macro", string[]> = {
  gold: [
    "Real yields rolled over while bullion held the 2,640 shelf — continuation into London fix.",
    "DXY impulse exhausted at the 156.4 pivot; gold bid reasserting on safe-haven rotation.",
    "MCX premium widened against COMEX; import duty desk sees physical demand into the evening.",
    "Silver/gold ratio compressing, dealer gamma pins spot above the weekly value area.",
    "ETF inflows accelerated for a third session; central-bank bid absorbed the Asia dump.",
  ],
  forex: [
    "EUR/USD defending the weekly VWAP while rate-differential flow turns positive.",
    "USD/JPY carry unwind is orderly; MoF intervention risk fades under 157.20.",
    "USD/INR fix bias neutral; RBI supply absorbed the importer bid at the open.",
    "London sweep cleared resting liquidity — expecting a fair-value gap fill.",
    "Cross-currency basis tightening, momentum regime flag flipped long dollar.",
  ],
  us: [
    "Nasdaq breadth improved to 68% while dealer gamma remains long above 21,300.",
    "Semis leading the tape on block accumulation; NVDA order-book support thickening.",
    "S&P realized vol below implied for six sessions — premium sellers exposed to a snap.",
    "US 10y drifted lower, growth factor risk premium compressing into the close.",
    "Options tape shows 0DTE call sweeps into the last hour — pin risk above 5,980.",
  ],
  india: [
    "Nifty heavies absorbed FII supply at the 24,050 shelf; breadth turned constructive.",
    "Bank Nifty PCR jumped to 1.28 with call writers unwinding into expiry.",
    "Sensex rel-strength vs MSCI EM hints at domestic SIP flow absorption.",
    "Midcap momentum broadening; small-cap hedge ratio at a two-month low.",
    "VIX compressed under 13 — breakout expansion likely above 24,250.",
  ],
  macro: [
    "Cross-asset correlation matrix flipped: gold and equities bidding together, dollar lagging.",
    "Global liquidity impulse turning up as the front-end reprices the policy path.",
    "Risk parity deleveraging complete; vol-target funds re-entering duration.",
    "EM capital flows improved for a second week, supporting INR and domestic equities.",
    "Term-premium shock would hit long-duration tech and bullion hedges asymmetrically.",
  ],
};

export const TIMEFRAMES = ["5m", "15m", "1H", "4H", "1D", "swing"];
