import { sql } from "drizzle-orm";
import { agents } from "@/db/schema";
import { databaseSchemaReady, db, isDatabaseConfigured, withDatabaseTimeout } from "@/db";

export const dynamic = "force-dynamic";

/**
 * Reports the actual PostgreSQL state; never claims a connection it lacks.
 *
 * Database readiness (connectivity + required read-only schema check) is
 * reported separately from agent-grid readiness. A hung database is bounded
 * by withDatabaseTimeout(), so health can never block a browser forever.
 *
 * 200 = database connected and schema present (simulation data persists).
 * 503 = database unconfigured/unavailable/schema-incomplete; the UI runs in
 *       read-only labelled synthetic demo mode. No secrets are exposed.
 */
async function probe(): Promise<{
  ok: boolean;
  database: "connected" | "unconfigured" | "unavailable" | "schema-incomplete";
  dataOrigin: "database-simulated" | "demo-synthetic";
  demoMode: boolean;
  detail?: string;
  remediation?: string;
  agents: { ready: boolean; source: "database" | "demo-synthetic"; count?: number };
}> {
  const demo = {
    ok: false,
    dataOrigin: "demo-synthetic" as const,
    demoMode: true,
    agents: { ready: false, source: "demo-synthetic" as const },
  };

  if (!isDatabaseConfigured()) {
    return {
      ...demo,
      database: "unconfigured",
      detail: "DATABASE_URL is not set. Terminal is running in read-only synthetic demo mode.",
      remediation: "Set DATABASE_URL in the Vercel project environment and apply the committed Drizzle migration.",
    };
  }

  try {
    await withDatabaseTimeout(db.execute(sql`select 1`));
    const schemaReady = await withDatabaseTimeout(databaseSchemaReady());
    if (!schemaReady) {
      return {
        ...demo,
        database: "schema-incomplete",
        detail: "Connected, but the required tables are missing. No migration was run.",
        remediation: "Apply the committed Drizzle migration manually; the app never modifies production schema.",
      };
    }
    // Agent-grid readiness is a separate, read-only count: an empty database
    // is connected but has no initialized agent profiles. No seeding here.
    const countResult = await withDatabaseTimeout(
      db.select({ count: sql<number>`count(*)::int` }).from(agents),
    );
    const agentCount = countResult[0]?.count ?? 0;
    return {
      ok: true,
      database: "connected",
      dataOrigin: "database-simulated",
      demoMode: false,
      agents: { ready: agentCount > 0, source: "database", count: agentCount },
    };
  } catch (error) {
    // Log full detail server-side; return only a fixed, non-sensitive reason.
    console.warn("database health probe failed:", error instanceof Error ? error.message : error);
    return {
      ...demo,
      database: "unavailable",
      detail: "Database connection timed out or failed. Terminal remains usable in read-only demo mode.",
      remediation: "Check DATABASE_URL and network access; no secrets are reported by this endpoint.",
    };
  }
}

export async function GET() {
  const result = await probe();
  return Response.json(result, { status: result.ok ? 200 : 503, headers: { "Cache-Control": "no-store" } });
}
