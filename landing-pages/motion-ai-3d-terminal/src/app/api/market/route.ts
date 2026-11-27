import { loadSnapshot } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

/**
 * Returns a snapshot. When the database is unavailable this returns a
 * clearly-labelled synthetic demo snapshot with HTTP 200 so the terminal
 * remains usable; `demo: true` and `dataOrigin: "demo-synthetic"` distinguish
 * it from database-backed simulation. Never claims live market data.
 */
export async function GET() {
  const { snapshot, demo, reason } = await loadSnapshot();
  return Response.json(
    { ...snapshot, demo, demoReason: reason },
    { headers: { "Cache-Control": "no-store, max-age=0" } },
  );
}
