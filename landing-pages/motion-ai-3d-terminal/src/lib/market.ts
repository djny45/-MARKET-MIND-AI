export type MarketKey = "gold" | "silver" | "crude" | "forex" | "us" | "india" | "crypto";

export type MarketMeta = {
  key: MarketKey;
  label: string;
  short: string;
  timezoneLabel: string;
  accent: string;
  description: string;
};

export const MARKETS: MarketMeta[] = [
  {
    key: "gold",
    label: "Gold",
    short: "GOLD",
    timezoneLabel: "XAU / COMEX / MCX",
    accent: "#F2C46B",
    description: "Spot bullion and MCX gold contracts",
  },
  {
    key: "silver",
    label: "Silver",
    short: "SILVER",
    timezoneLabel: "XAG / COMEX / MCX",
    accent: "#C7D0DB",
    description: "Spot silver, MCX silver and the gold/silver ratio",
  },
  {
    key: "crude",
    label: "Crude Oil",
    short: "CRUDE",
    timezoneLabel: "WTI / BRENT / MCX",
    accent: "#E07A5F",
    description: "WTI, Brent and MCX crude research panels",
  },
  {
    key: "forex",
    label: "Forex / FX",
    short: "FX",
    timezoneLabel: "LDN · NY · MUM",
    accent: "#5BE9E0",
    description: "Majors, yen cross and USD/INR",
  },
  {
    key: "us",
    label: "USA Markets",
    short: "US",
    timezoneLabel: "NYSE · NASDAQ",
    accent: "#8AB4FF",
    description: "US index futures and mega-cap tech",
  },
  {
    key: "india",
    label: "India Markets",
    short: "IN",
    timezoneLabel: "NSE · BSE",
    accent: "#5BE39A",
    description: "Nifty, Sensex and Bank Nifty",
  },
  {
    key: "crypto",
    label: "Crypto (Research)",
    short: "CRYPTO",
    timezoneLabel: "24/7 SPOT",
    accent: "#F7931A",
    description: "Synthetic BTC/ETH spot research panels — not live prices",
  },
];

export const MARKET_MAP: Record<MarketKey, MarketMeta> = MARKETS.reduce(
  (acc, market) => ({ ...acc, [market.key]: market }),
  {} as Record<MarketKey, MarketMeta>,
);

export function isMarketKey(value: string | null | undefined): value is MarketKey {
  return ["gold", "silver", "crude", "forex", "us", "india", "crypto"].includes(value ?? "");
}

export type InstrumentDefinition = {
  symbol: string;
  name: string;
  market: MarketKey;
  kind: string;
  currency: string;
  unit: string;
  decimals: number;
  basePrice: number;
  volatility: number;
  volumeBase: number;
};

export const INSTRUMENT_DEFINITIONS: InstrumentDefinition[] = [
  {
    symbol: "XAU/USD",
    name: "Gold Spot",
    market: "gold",
    kind: "spot",
    currency: "USD",
    unit: "per troy oz",
    decimals: 2,
    basePrice: 2648.4,
    volatility: 0.0011,
    volumeBase: 184_000,
  },
  {
    symbol: "XAG/USD",
    name: "Silver Spot",
    market: "silver",
    kind: "spot",
    currency: "USD",
    unit: "per troy oz",
    decimals: 3,
    basePrice: 31.42,
    volatility: 0.0018,
    volumeBase: 96_000,
  },
  {
    symbol: "MCX:SILVER",
    name: "MCX Silver Mar",
    market: "silver",
    kind: "future",
    currency: "INR",
    unit: "per kg",
    decimals: 0,
    basePrice: 92_450,
    volatility: 0.0021,
    volumeBase: 38_000,
  },
  {
    symbol: "WTI",
    name: "WTI Crude",
    market: "crude",
    kind: "future",
    currency: "USD",
    unit: "per barrel",
    decimals: 2,
    basePrice: 71.35,
    volatility: 0.0026,
    volumeBase: 214_000,
  },
  {
    symbol: "BRENT",
    name: "Brent Crude",
    market: "crude",
    kind: "future",
    currency: "USD",
    unit: "per barrel",
    decimals: 2,
    basePrice: 74.82,
    volatility: 0.0024,
    volumeBase: 186_000,
  },
  {
    symbol: "MCX:CRUDE",
    name: "MCX Crude",
    market: "crude",
    kind: "future",
    currency: "INR",
    unit: "per barrel",
    decimals: 1,
    basePrice: 6_124.5,
    volatility: 0.0027,
    volumeBase: 74_000,
  },
  {
    symbol: "MCX:GOLD",
    name: "MCX Gold Feb",
    market: "gold",
    kind: "future",
    currency: "INR",
    unit: "per 10g",
    decimals: 0,
    basePrice: 78_940,
    volatility: 0.0012,
    volumeBase: 42_500,
  },
  {
    symbol: "EUR/USD",
    name: "Euro / Dollar",
    market: "forex",
    kind: "spot",
    currency: "USD",
    unit: "per EUR",
    decimals: 5,
    basePrice: 1.0842,
    volatility: 0.00042,
    volumeBase: 512_000,
  },
  {
    symbol: "USD/JPY",
    name: "Dollar / Yen",
    market: "forex",
    kind: "spot",
    currency: "JPY",
    unit: "per USD",
    decimals: 3,
    basePrice: 156.284,
    volatility: 0.00055,
    volumeBase: 388_000,
  },
  {
    symbol: "USD/INR",
    name: "Dollar / Rupee",
    market: "forex",
    kind: "spot",
    currency: "INR",
    unit: "per USD",
    decimals: 3,
    basePrice: 84.612,
    volatility: 0.00028,
    volumeBase: 274_000,
  },
  {
    symbol: "NDX",
    name: "Nasdaq 100",
    market: "us",
    kind: "index",
    currency: "USD",
    unit: "index",
    decimals: 2,
    basePrice: 21_412.8,
    volatility: 0.0013,
    volumeBase: 624_000,
  },
  {
    symbol: "SPX",
    name: "S&P 500",
    market: "us",
    kind: "index",
    currency: "USD",
    unit: "index",
    decimals: 2,
    basePrice: 5_982.4,
    volatility: 0.0011,
    volumeBase: 712_000,
  },
  {
    symbol: "NVDA",
    name: "Nvidia Corp",
    market: "us",
    kind: "equity",
    currency: "USD",
    unit: "per share",
    decimals: 2,
    basePrice: 146.28,
    volatility: 0.0024,
    volumeBase: 348_000,
  },
  {
    symbol: "NIFTY",
    name: "Nifty 50",
    market: "india",
    kind: "index",
    currency: "INR",
    unit: "index",
    decimals: 2,
    basePrice: 24_118.35,
    volatility: 0.0011,
    volumeBase: 288_000,
  },
  {
    symbol: "SENSEX",
    name: "BSE Sensex",
    market: "india",
    kind: "index",
    currency: "INR",
    unit: "index",
    decimals: 2,
    basePrice: 79_402.16,
    volatility: 0.0011,
    volumeBase: 194_000,
  },
  {
    symbol: "BANKNIFTY",
    name: "Bank Nifty",
    market: "india",
    kind: "index",
    currency: "INR",
    unit: "index",
    decimals: 2,
    basePrice: 51_684.7,
    volatility: 0.0015,
    volumeBase: 168_000,
  },
  // Synthetic crypto research panels. Base prices are static demo anchors,
  // not live quotes; the terminal labels all values demo-synthetic.
  {
    symbol: "BTC/USD",
    name: "Bitcoin (Synthetic)",
    market: "crypto",
    kind: "spot",
    currency: "USD",
    unit: "per BTC",
    decimals: 2,
    basePrice: 96_420.5,
    volatility: 0.0028,
    volumeBase: 128_000,
  },
  {
    symbol: "ETH/USD",
    name: "Ethereum (Synthetic)",
    market: "crypto",
    kind: "spot",
    currency: "USD",
    unit: "per ETH",
    decimals: 2,
    basePrice: 3_412.75,
    volatility: 0.0034,
    volumeBase: 96_000,
  },
];

export type MarketSession = {
  market: MarketKey;
  status: "open" | "closed" | "pre" | "post";
  label: string;
  detail: string;
};

type SessionWindow = {
  /** Minutes from UTC midnight. */
  open: number;
  close: number;
  weekdayOnly: boolean;
};

const SESSION_WINDOWS: Record<MarketKey, SessionWindow> = {
  gold: { open: 23 * 60, close: 21 * 60, weekdayOnly: false },
  silver: { open: 23 * 60, close: 21 * 60, weekdayOnly: false },
  crude: { open: 23 * 60, close: 21 * 60, weekdayOnly: false },
  forex: { open: 22 * 60, close: 21 * 60, weekdayOnly: false },
  us: { open: 14 * 60 + 30, close: 21 * 60, weekdayOnly: true },
  india: { open: 3 * 60 + 45, close: 10 * 60, weekdayOnly: true },
  crypto: { open: 0, close: 24 * 60, weekdayOnly: false },
};

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

function formatWindow(minutes: number): string {
  const normalized = ((minutes % 1440) + 1440) % 1440;
  return `${pad(Math.floor(normalized / 60))}:${pad(normalized % 60)} UTC`;
}

export function marketSessions(now: Date = new Date()): MarketSession[] {
  const utcMinutes = now.getUTCHours() * 60 + now.getUTCMinutes();
  const day = now.getUTCDay(); // 0 = Sunday

  return MARKETS.map((market) => {
    const window = SESSION_WINDOWS[market.key];
    const weekend = day === 6 || day === 0;

    if (market.key === "crypto") {
      // Crypto spot trades continuously; no exchange-hours claim is made.
      return {
        market: market.key,
        status: "open" as const,
        label: "24/7",
        detail: "continuous synthetic research panel",
      } satisfies MarketSession;
    }

    if (window.weekdayOnly) {
      const open = !weekend && utcMinutes >= window.open && utcMinutes < window.close;
      const pre = !weekend && utcMinutes >= window.open - 60 && utcMinutes < window.open;
      return {
        market: market.key,
        status: open ? "open" : pre ? "pre" : "closed",
        label: open ? "OPEN" : pre ? "PRE-MARKET" : "CLOSED",
        detail: open
          ? `closes ${formatWindow(window.close)}`
          : pre
            ? `opens ${formatWindow(window.open)}`
            : `next open ${formatWindow(window.open)}`,
      } satisfies MarketSession;
    }

    const closedForWeek = day === 6 || (day === 0 && utcMinutes < window.open) || (day === 5 && utcMinutes >= window.close);
    return {
      market: market.key,
      status: closedForWeek ? "closed" : "open",
      label: closedForWeek ? "CLOSED" : "OPEN",
      detail: closedForWeek ? "reopens Sun 22:00 UTC" : "24/5 continuous",
    } satisfies MarketSession;
  });
}

export function marketSessionFor(market: MarketKey, now: Date = new Date()): MarketSession {
  return marketSessions(now).find((session) => session.market === market) ?? {
    market,
    status: "closed",
    label: "CLOSED",
    detail: "",
  };
}

export function formatPrice(value: number, decimals = 2): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatSigned(value: number, decimals = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
