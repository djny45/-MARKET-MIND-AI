import { readResearchBars } from "@/lib/researchBars";

export const dynamic = "force-dynamic";

/**
 * Read-only, opt-in research bars from the operator's attested local feed.
 * Disabled by default (MARKET_MIND_RESEARCH_DB unset). No credentials, no
 * writes, no browser-side privileged access. The payload always declares its
 * provenance and staleness; it is never described as live/execution-grade.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const requested = url.searchParams.get("symbols");
  const symbols = (requested ?? "BTCUSD,ETHUSD,SOLUSD,BNBUSD")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter((s) => /^[A-Z0-9/]{3,20}$/.test(s))
    .slice(0, 12);
  return Response.json(readResearchBars(symbols), {
    headers: { "Cache-Control": "no-store" },
  });
}
