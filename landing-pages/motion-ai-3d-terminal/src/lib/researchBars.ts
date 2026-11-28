/**
 * Optional, server-side, read-only bridge to operator-attested research bars.
 *
 * This is deliberately NOT the terminal's PostgreSQL `DATABASE_URL`. It reads
 * the local backend SQLite database only when MARKET_MIND_RESEARCH_DB is set
 * to an explicit path. It never writes, never logs the path/DSN, and never
 * leaves this module: browsers receive only the selected public research bars.
 *
 * Data is labelled `binance-public-research`: a 15-minute public-exchange
 * research feed, not a licensed real-time feed and not execution-grade.
 */

import { DatabaseSync } from "node:sqlite";

export type ResearchBar = {
  symbol: string;
  interval: string;
  timestamp: string;
  retrievedAt: string;
  close: number;
  source: string;
  status: string;
};

export type ResearchBarsResult = {
  enabled: boolean;
  available: boolean;
  dataOrigin: "binance-public-research";
  bars: ResearchBar[];
  asOf: string | null;
  /** Minutes between the newest bar timestamp and its retrieval time. */
  freshnessMinutes: number | null;
  stale: boolean;
  detail: string;
};

const STALE_AFTER_MINUTES = 60;

function empty(disabled: boolean, detail: string): ResearchBarsResult {
  return {
    enabled: !disabled,
    available: false,
    dataOrigin: "binance-public-research",
    bars: [],
    asOf: null,
    freshnessMinutes: null,
    stale: false,
    detail,
  };
}

/**
 * Read the latest attested live bars for the requested symbols.
 * Returns a disabled/unavailable result instead of throwing so the terminal
 * remains fully functional without this optional research database.
 */
export function readResearchBars(symbols: string[]): ResearchBarsResult {
  const path = process.env.MARKET_MIND_RESEARCH_DB?.trim();
  if (!path) return empty(true, "MARKET_MIND_RESEARCH_DB is not set; research bars unavailable.");
  if (symbols.length === 0) return empty(false, "No symbols requested.");

  let db: DatabaseSync | null = null;
  try {
    db = new DatabaseSync(path, { readOnly: true });
    // Fail closed on any non-attested source: only this exact source/status is read.
    const placeholders = symbols.map(() => "?").join(",");
    const rows = db.prepare(
      `SELECT symbol, interval, timestamp, retrieved_at, close, source, status
       FROM market_bars
       WHERE source = 'binance-public' AND status = 'live' AND symbol IN (${placeholders})
       ORDER BY timestamp DESC`,
    ).all(...symbols) as {
      symbol: string;
      interval: string;
      timestamp: string;
      retrieved_at: string;
      close: number;
      source: string;
      status: string;
    }[];

    const bars: ResearchBar[] = rows.map((row) => ({
      symbol: row.symbol,
      interval: row.interval,
      timestamp: row.timestamp,
      retrievedAt: row.retrieved_at,
      close: Number(row.close),
      source: row.source,
      status: row.status,
    }));
    if (bars.length === 0) {
      return { ...empty(false, "No attested live research bars found."), enabled: true };
    }

    const newest = bars[0];
    const asOf = newest.retrievedAt;
    const freshnessMinutes = Math.max(
      0,
      Math.round((Date.parse(newest.retrievedAt) - Date.parse(newest.timestamp)) / 60_000),
    );
    // Also guard against an old retrieval regardless of bar timestamp.
    const retrievalAgeMinutes = Math.max(0, Math.round((Date.now() - Date.parse(newest.retrievedAt)) / 60_000));
    const stale = retrievalAgeMinutes > STALE_AFTER_MINUTES || freshnessMinutes > STALE_AFTER_MINUTES;
    return {
      enabled: true,
      available: true,
      dataOrigin: "binance-public-research",
      bars,
      asOf,
      freshnessMinutes,
      stale,
      detail: stale
        ? `Attested research bars are stale (last retrieved ${retrievalAgeMinutes} min ago).`
        : "Operator-attested binance-public 15m research bars. Not live/execution-grade data.",
    };
  } catch {
    // Never expose the path, SQL or exception text to the browser.
    return { ...empty(false, "Research bar database could not be read."), enabled: true };
  } finally {
    db?.close();
  }
}
