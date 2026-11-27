import { sql } from "drizzle-orm";
import { db, isDatabaseConfigured } from "@/db";

export const dynamic = "force-dynamic";

/**
 * Reports the actual PostgreSQL state; never claims a connection it lacks.
 *
 * 200 = database connected (simulation data persists).
 * 503 = database unconfigured/unavailable; the UI runs in read-only labelled
 *       synthetic demo mode. This is an honest, usable state, not a failure
 *       of the application itself.
 */
export async function GET() {
  if (!isDatabaseConfigured()) {
    return Response.json(
      {
        ok: false,
        database: "unconfigured",
        dataOrigin: "demo-synthetic",
        demoMode: true,
        detail: "DATABASE_URL is not set. Terminal is running in read-only synthetic demo mode.",
        remediation: "Set DATABASE_URL in the Vercel project environment and apply the committed Drizzle migration.",
      },
      { status: 503 },
    );
  }
  try {
    await db.execute(sql`select 1`);
    return Response.json({
      ok: true,
      database: "connected",
      dataOrigin: "database-simulated",
      demoMode: false,
    });
  } catch (error) {
    return Response.json(
      {
        ok: false,
        database: "unavailable",
        dataOrigin: "demo-synthetic",
        demoMode: true,
        detail: error instanceof Error ? error.message.slice(0, 200) : "connection failed",
        remediation: "Check DATABASE_URL and network access; the terminal remains usable in read-only demo mode.",
      },
      { status: 503 },
    );
  }
}
