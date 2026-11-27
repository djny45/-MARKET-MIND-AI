import { buildDemoSnapshot } from "@/lib/demoSnapshot";
import { getRecentSignals } from "@/lib/engine";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Math.min(80, Math.max(1, Number(url.searchParams.get("limit") ?? "24") || 24));
  try {
    const signals = await getRecentSignals(limit);
    return Response.json(
      { signals, dataOrigin: "database-simulated" },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    // Read-only synthetic demo fallback; never claim database connectivity.
    const signals = buildDemoSnapshot().signals.slice(0, limit);
    return Response.json(
      { signals, dataOrigin: "demo-synthetic", demo: true },
      { headers: { "Cache-Control": "no-store" } },
    );
  }
}
