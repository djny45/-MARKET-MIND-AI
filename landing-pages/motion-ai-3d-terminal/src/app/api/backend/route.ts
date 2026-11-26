import { probeMarketMindBackend } from "@/lib/marketMindAdapter";

export const dynamic = "force-dynamic";

/** Read-only probe of the optional MARKET-MIND-AI backend. */
export async function GET(request: Request) {
  const snapshot = await probeMarketMindBackend(request.signal);
  return Response.json(snapshot, {
    headers: { "Cache-Control": "no-store" },
    status: snapshot.status === "disabled" ? 200 : 200,
  });
}
