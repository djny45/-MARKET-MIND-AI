/**
 * Optional adapter to the existing MARKET-MIND-AI FastAPI research backend.
 *
 * This is deliberately separate from the vendored simulated engine. It is
 * disabled unless MARKET_MIND_API_URL is set; the landing page stays fully
 * runnable on its own. Only documented, read-only endpoints are used:
 *   GET /api/health, /api/providers/status, /api/workers,
 *       /api/daily/status, /api/daily/schedule
 *
 * No broker, order-routing, wallet or trading endpoint is referenced.
 */
export type BackendStatus =
  | "disabled"
  | "connected"
  | "unavailable"
  | "authentication_required";

export type BackendSnapshot = {
  status: BackendStatus;
  detail?: string;
  checkedAt: string;
  workers?: number;
  providers?: string[];
  dataOrigin: "market-mind-backend" | "local-simulation";
};

const TIMEOUT_MS = Number(process.env.MARKET_MIND_API_TIMEOUT_MS ?? 5000);
const BASE = process.env.MARKET_MIND_API_URL?.replace(/\/$/, "") ?? "";

export function isBackendConfigured(): boolean {
  return BASE.length > 0;
}

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Number.isFinite(TIMEOUT_MS) ? TIMEOUT_MS : 5000);
  const forward = () => controller.abort();
  signal?.addEventListener("abort", forward, { once: true });
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    const token = process.env.MARKET_MIND_API_TOKEN?.trim();
    if (token) headers.Authorization = `Bearer ${token}`;
    // Allow this server-side read-only probe to reach the protected Vercel preview.
    // The secret is stored only in the landing project environment, never sent to browsers.
    const vercelBypass = process.env.MARKET_MIND_VERCEL_BYPASS?.trim();
    if (vercelBypass) headers["x-vercel-protection-bypass"] = vercelBypass;
    const response = await fetch(`${BASE}${path}`, {
      headers,
      cache: "no-store",
      signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) {
      throw new Error("authentication_required");
    }
    if (!response.ok) throw new Error(`backend_http_${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forward);
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

/** Read-only health + inventory probe with bounded timeout and honest status. */
export async function probeMarketMindBackend(signal?: AbortSignal): Promise<BackendSnapshot> {
  const checkedAt = new Date().toISOString();
  if (!isBackendConfigured()) {
    return { status: "disabled", checkedAt, dataOrigin: "local-simulation" };
  }
  try {
    const health = asRecord(await getJson("/api/health", signal));
    if (!health || health.status !== "ok") throw new Error("backend_unhealthy");
    const [workers, providers] = await Promise.all([
      getJson("/api/workers", signal).catch(() => null),
      getJson("/api/providers/status", signal).catch(() => null),
    ]);
    const workerRecord = asRecord(workers);
    const providerRecord = asRecord(providers);
    return {
      status: "connected",
      checkedAt,
      workers: typeof workerRecord?.count === "number" ? workerRecord.count : undefined,
      providers: Array.isArray(providerRecord?.live_providers)
        ? (providerRecord.live_providers as unknown[]).filter((p): p is string => typeof p === "string")
        : Array.isArray(providerRecord?.available_adapters)
          ? (providerRecord.available_adapters as unknown[])
              .map((item) => asRecord(item)?.name)
              .filter((name): name is string => typeof name === "string")
          : undefined,
      dataOrigin: "market-mind-backend",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown";
    const status: BackendStatus =
      message === "authentication_required" ? "authentication_required" : "unavailable";
    return { status, detail: message.slice(0, 120), checkedAt, dataOrigin: "local-simulation" };
  }
}
