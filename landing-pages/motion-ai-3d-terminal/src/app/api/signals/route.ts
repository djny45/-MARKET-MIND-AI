import { isDatabaseConfigured, withDatabaseTimeout } from "@/db";
import { buildDemoSnapshot } from "@/lib/demoSnapshot";
import { getRecentSignals } from "@/lib/engine";

export const dynamic = "force-dynamic";

const NO_STORE = { headers: { "Cache-Control": "no-store" } };

function demoSignals(limit: number) {
  // Read-only synthetic fallback; never claims database connectivity.
  return Response.json(
    { signals: buildDemoSnapshot().signals.slice(0, limit), dataOrigin: "demo-synthetic", demo: true },
    NO_STORE,
  );
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Math.min(80, Math.max(1, Number(url.searchParams.get("limit") ?? "24") || 24));
  if (!isDatabaseConfigured()) return demoSignals(limit);
  try {
    const signals = await withDatabaseTimeout(getRecentSignals(limit));
    return Response.json({ signals, dataOrigin: "database-simulated" }, NO_STORE);
  } catch {
    return demoSignals(limit);
  }
}
