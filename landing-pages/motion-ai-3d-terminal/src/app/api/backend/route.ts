import { probeMarketMindBackend } from "@/lib/marketMindAdapter";

export const dynamic = "force-dynamic";

/** Read-only probe of the optional MARKET-MIND-AI backend. */
export async function GET(request: Request) {
  const snapshot = await probeMarketMindBackend(request.signal);
  // The probe is informational: a disabled/unavailable backend is a valid
  // state for this standalone demo, not an HTTP error. The status field in
  // the payload carries the distinction; the client renders it as a pill.
  return Response.json(snapshot, {
    headers: { "Cache-Control": "no-store" },
    status: 200,
  });
}
