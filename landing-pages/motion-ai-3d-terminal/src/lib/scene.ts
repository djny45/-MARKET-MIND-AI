import type { AgentStats } from "./types";

export type SceneTelemetry = {
  /** Share of the swarm actively working the tape (0–1). */
  activity: number;
  /** Signal velocity across the whole swarm (0–1). */
  velocity: number;
  /** Blended reactive energy (0–1). */
  energy: number;
  /** Live `speed` handed to the Gateway Flow scene. */
  speed: number;
  /** Live `opacity` handed to the Gateway Flow scene. */
  opacity: number;
  /** Agents currently engaged (active + scanning + debating). */
  working: number;
};

/**
 * Maps all 550 agents onto the single reactive Gateway Flow scene.
 *
 * Only `speed` and `opacity` are driven live: the ThreeUI component rebuilds
 * its canonical document for baked geometry knobs (`size`, `density`, `length`,
 * `gap`), so those stay pinned at the configured `1.00`.
 */
export function deriveSceneTelemetry(stats: AgentStats, signalCount: number): SceneTelemetry {
  const total = Math.max(1, stats.total);
  const working = stats.active + stats.scanning + stats.debating;
  const activity = Math.min(1, working / total);
  const velocity = Math.min(1, signalCount / 20);
  const energy = Math.min(1, activity * 0.6 + velocity * 0.4);

  return {
    activity,
    velocity,
    energy,
    working,
    speed: Number((0.75 + energy * 1.65).toFixed(2)),
    opacity: Number((0.62 + energy * 0.38).toFixed(2)),
  };
}
