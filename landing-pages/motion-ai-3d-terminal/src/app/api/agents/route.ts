import { buildDemoAgentDirectory } from "@/lib/demoSnapshot";
import { listAgents } from "@/lib/engine";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const query = {
    q: url.searchParams.get("q") ?? undefined,
    focus: url.searchParams.get("focus") ?? undefined,
    status: url.searchParams.get("status") ?? undefined,
    sort: url.searchParams.get("sort") ?? undefined,
    page: Number(url.searchParams.get("page") ?? "1") || 1,
    perPage: Number(url.searchParams.get("perPage") ?? "12") || 12,
  };
  try {
    const result = await listAgents(query);
    return Response.json(
      { ...result, dataOrigin: "database-simulated" },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    // Keep the terminal usable, but make the fallback visible in server logs
    // so a real query defect is not silently masked as "demo mode".
    console.warn("agent directory fell back to demo data:", error instanceof Error ? error.message : error);
    return Response.json(buildDemoAgentDirectory(query), {
      headers: { "Cache-Control": "no-store" },
    });
  }
}
