/**
 * Single entry point for market snapshots.
 *
 * Tries the real (simulated, database-backed) engine first. If PostgreSQL is
 * missing or unreachable, falls back to a clearly-labelled read-only
 * synthetic demo snapshot so the terminal stays usable. This never claims
 * database connectivity it does not have.
 */

import { isDatabaseConfigured, withDatabaseTimeout } from "@/db";
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

function demoResult(): SnapshotResult {
  return { snapshot: buildDemoSnapshot(), demo: true, reason: DEMO_REASON };
}

/**
 * Load a snapshot with a bounded first attempt and at most one bounded retry.
 * A missing DATABASE_URL needs no retry at all; a hung or black-holed
 * database can never leave the page waiting forever. After the deadline the
 * labelled read-only demo snapshot is served instead.
 */
export async function loadSnapshot(): Promise<SnapshotResult> {
  if (!isDatabaseConfigured()) return demoResult();

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const snapshot = await withDatabaseTimeout(getSnapshot());
      return { snapshot, demo: false, reason: null };
    } catch (error) {
      const detail = error instanceof Error ? error.message.slice(0, 200) : "unknown error";
      console.warn(
        `database snapshot attempt ${attempt} failed${attempt === 1 ? "; retrying" : "; using labelled synthetic demo"}:`,
        detail,
      );
    }
  }
  return demoResult();
}
