/**
 * Single entry point for market snapshots.
 *
 * Tries the real (simulated, database-backed) engine first. If PostgreSQL is
 * missing or unreachable, falls back to a clearly-labelled read-only
 * synthetic demo snapshot so the terminal stays usable. This never claims
 * database connectivity it does not have.
 */

import { buildDemoSnapshot } from "./demoSnapshot";
import { getSnapshot } from "./engine";
import type { MarketSnapshot } from "./types";

export type SnapshotResult = {
  snapshot: MarketSnapshot;
  demo: boolean;
  reason: string | null;
};

export async function loadSnapshot(): Promise<SnapshotResult> {
  try {
    return { snapshot: await getSnapshot(), demo: false, reason: null };
  } catch (error) {
    const reason =
      error instanceof Error ? error.message.slice(0, 200) : "unknown error";
    console.warn("database unavailable; using labelled synthetic demo:", reason);
    return { snapshot: buildDemoSnapshot(), demo: true, reason };
  }
}
