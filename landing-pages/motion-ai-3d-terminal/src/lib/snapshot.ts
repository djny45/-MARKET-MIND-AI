/**
 * Single entry point for market snapshots.
 *
 * Tries the real (simulated, database-backed) engine first. If PostgreSQL is
 * missing or unreachable, falls back to a clearly-labelled read-only
 * synthetic demo snapshot so the terminal stays usable. This never claims
 * database connectivity it does not have.
 */

import { withDatabaseTimeout } from "@/db";
import { buildDemoSnapshot } from "./demoSnapshot";
import { getSnapshot } from "./engine";
import type { MarketSnapshot } from "./types";

export type SnapshotResult = {
  snapshot: MarketSnapshot;
  demo: boolean;
  reason: string | null;
};

/** Fixed, non-sensitive reason: no host, port or internal topology is exposed. */
const DEMO_REASON = "database unavailable or not configured";

/**
 * Load a snapshot with a bounded first attempt and one bounded retry.
 * A hung or black-holed database can never leave the page waiting forever:
 * after the deadline the labelled read-only demo snapshot is served instead.
 */
export async function loadSnapshot(): Promise<SnapshotResult> {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const snapshot = await withDatabaseTimeout(getSnapshot());
      return { snapshot, demo: false, reason: null };
    } catch (error) {
      const detail = error instanceof Error ? error.message.slice(0, 200) : "unknown error";
      if (attempt === 2) {
        console.warn(`database unavailable after ${attempt} attempts; using labelled synthetic demo:`, detail);
        return { snapshot: buildDemoSnapshot(), demo: true, reason: DEMO_REASON };
      }
      console.warn(`database snapshot attempt ${attempt} failed; retrying:`, detail);
    }
  }
  // Unreachable in practice, but keeps the return type total.
  return { snapshot: buildDemoSnapshot(), demo: true, reason: DEMO_REASON };
}
