import { sql } from "drizzle-orm";
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

/**
 * Lazy database connection.
 *
 * The vendored source threw at module import when DATABASE_URL was absent,
 * which broke `next build`, the homepage and /api/health on any machine
 * without PostgreSQL. This version keeps the Drizzle/pg implementation
 * unchanged but defers construction until the first query. The health route
 * can then report the real state and the UI can show its fallback screen.
 */
const globalForDb = globalThis as typeof globalThis & {
  __arenaNextJsPostgresqlPool?: Pool;
  __arenaNextJsPostgresqlDb?: NodePgDatabase;
};

export function databaseUrl(): string | null {
  const value = process.env.DATABASE_URL?.trim();
  return value ? value : null;
}

export function isDatabaseConfigured(): boolean {
  return databaseUrl() !== null;
}

/**
 * Hard cap for any single database initialization attempt. Without this, an
 * unreachable DATABASE_URL makes pg retry indefinitely and the browser sits
 * on "awaiting database handshake" forever. The cap is a ceiling, not a
 * promise of success: callers fall back to labelled demo mode when it trips.
 */
export const DATABASE_TIMEOUT_MS = Number(process.env.DATABASE_TIMEOUT_MS ?? 4000);

export function getPool(): Pool {
  const url = databaseUrl();
  if (!url) {
    throw new Error("DATABASE_URL is not configured");
  }
  if (!globalForDb.__arenaNextJsPostgresqlPool) {
    const budget = Number.isFinite(DATABASE_TIMEOUT_MS) && DATABASE_TIMEOUT_MS > 0
      ? DATABASE_TIMEOUT_MS
      : 4000;
    const pool = new Pool({
      connectionString: url,
      connectionTimeoutMillis: budget,
      query_timeout: budget,
      idleTimeoutMillis: 10_000,
      max: 4,
    });
    // pg emits idle-client errors; without a listener Node can crash on them.
    pool.on("error", (error) => console.warn("pg pool error:", error.message));
    globalForDb.__arenaNextJsPostgresqlPool = pool;
  }
  return globalForDb.__arenaNextJsPostgresqlPool;
}

/**
 * Reject a database operation after a bounded delay even if the driver stalls.
 * Browsers and Vercel functions must never wait forever on a dead database.
 */
export async function withDatabaseTimeout<T>(work: Promise<T>): Promise<T> {
  const budget = Number.isFinite(DATABASE_TIMEOUT_MS) && DATABASE_TIMEOUT_MS > 0
    ? DATABASE_TIMEOUT_MS
    : 4000;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      work,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(`database_timeout_${budget}ms`)), budget);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** Read-only schema check: confirms required tables exist without altering data. */
export async function databaseSchemaReady(): Promise<boolean> {
  const result = await db.execute(sql`
    select count(distinct table_name)::int as "tableCount"
    from information_schema.tables
    where table_schema = current_schema()
      and table_name in ('instruments', 'candles', 'agents', 'signals', 'agent_events')
  `);
  const rows = (result as unknown as { rows?: { tableCount: number }[] }).rows;
  return (rows?.[0]?.tableCount ?? 0) === 5;
}

/** Proxy used by the existing `@/db` imports; resolves the real client lazily. */
export const db: NodePgDatabase = new Proxy({} as NodePgDatabase, {
  get(_target, property, receiver) {
    if (!globalForDb.__arenaNextJsPostgresqlDb) {
      globalForDb.__arenaNextJsPostgresqlDb = drizzle(getPool());
    }
    const value = Reflect.get(globalForDb.__arenaNextJsPostgresqlDb, property, receiver);
    return typeof value === "function" ? value.bind(globalForDb.__arenaNextJsPostgresqlDb) : value;
  },
});
