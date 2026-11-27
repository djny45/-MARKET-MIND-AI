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

export function getPool(): Pool {
  const url = databaseUrl();
  if (!url) {
    throw new Error("DATABASE_URL is not configured");
  }
  if (!globalForDb.__arenaNextJsPostgresqlPool) {
    globalForDb.__arenaNextJsPostgresqlPool = new Pool({ connectionString: url });
  }
  return globalForDb.__arenaNextJsPostgresqlPool;
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
