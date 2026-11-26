import { sql } from "drizzle-orm";
import { db, isDatabaseConfigured } from "@/db";

export const dynamic = "force-dynamic";

/** Reports the actual PostgreSQL state; never claims a connection it lacks. */
export async function GET() {
  if (!isDatabaseConfigured()) {
    return Response.json(
      { ok: false, database: "unconfigured", detail: "DATABASE_URL is not set" },
      { status: 503 },
    );
  }
  try {
    await db.execute(sql`select 1`);
    return Response.json({ ok: true, database: "connected" });
  } catch (error) {
    return Response.json(
      {
        ok: false,
        database: "unavailable",
        detail: error instanceof Error ? error.message.slice(0, 200) : "connection failed",
      },
      { status: 503 },
    );
  }
}
