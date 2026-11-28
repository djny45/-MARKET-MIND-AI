import { isDatabaseConfigured, withDatabaseTimeout } from "@/db";
import { buildDemoSnapshot } from "@/lib/demoSnapshot";
import { runSwarmScan } from "@/lib/engine";

export const dynamic = "force-dynamic";

const NO_STORE = { headers: { "Cache-Control": "no-store" } };

function demoScan(count: number) {
  // Read-only demo: no persistence, no writes. Clearly labelled synthetic.
  const snapshot = buildDemoSnapshot();
  return Response.json(
    {
      signals: snapshot.signals.slice(0, Math.min(10, Math.max(1, count))),
      consensus: snapshot.consensus,
      dataOrigin: "demo-synthetic",
      demo: true,
    },
    NO_STORE,
  );
}

export async function POST(request: Request) {
  let count = 4;
  try {
    const body = (await request.json()) as { count?: number } | null;
    if (body && typeof body.count === "number") count = body.count;
  } catch {
    // body is optional
  }

  if (!isDatabaseConfigured()) return demoScan(count);
  try {
    const result = await withDatabaseTimeout(runSwarmScan(count));
    return Response.json({ ...result, dataOrigin: "database-simulated" }, NO_STORE);
  } catch {
    return demoScan(count);
  }
}
