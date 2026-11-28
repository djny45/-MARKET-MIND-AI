#!/usr/bin/env node
/**
 * Regression: an unreachable DATABASE_URL must never leave the terminal
 * waiting forever. Starts a local production server against a black-holed
 * address, then asserts every browser-facing request settles within a bound
 * and falls back to the labelled demo snapshot.
 *
 *   node scripts/verify-unreachable-db.mjs
 *
 * No credentials are read, printed or written to any database.
 */
import { spawn } from "node:child_process";

const PORT = 3125;
const BASE = `http://127.0.0.1:${PORT}`;
const DEADLINE_MS = 12_000;
// RFC 5737 TEST-NET address: guaranteed non-routable, no real database.
const DATABASE_URL = "postgresql://probe:probe@203.0.113.1:5432/unreachable";

const failures = [];
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(name);
}

async function waitForServer() {
  for (let i = 0; i < 40; i += 1) {
    try {
      const r = await fetch(`${BASE}/icon.svg`, { signal: AbortSignal.timeout(1000) });
      if (r.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("server did not start");
}

async function timed(path) {
  const started = Date.now();
  const response = await fetch(`${BASE}${path}`, {
    signal: AbortSignal.timeout(DEADLINE_MS),
    cache: "no-store",
  });
  const text = await response.text();
  return { status: response.status, ms: Date.now() - started, text };
}

const child = spawn("npm", ["run", "start", "--", "-p", String(PORT)], {
  env: { ...process.env, DATABASE_URL, DATABASE_TIMEOUT_MS: "3000" },
  stdio: ["ignore", "pipe", "pipe"],
  detached: true,
});
let serverLog = "";
child.stdout.on("data", (chunk) => { serverLog += chunk.toString(); });
child.stderr.on("data", (chunk) => { serverLog += chunk.toString(); });

try {
  await waitForServer();

  for (const [path, expectOrigin] of [["/", "demo-synthetic"], ["/api/market", "demo-synthetic"], ["/api/health", null]]) {
    try {
      const result = await timed(path);
      check(`${path} responds within ${DEADLINE_MS}ms`, result.ms < DEADLINE_MS, `${result.ms}ms status=${result.status}`);
      if (path === "/" || path === "/api/market") {
        check(`${path} uses labelled demo fallback`, result.text.includes(expectOrigin), `origin label present=${result.text.includes(expectOrigin)}`);
        check(`${path} has no boot screen`, !result.text.includes("awaiting database handshake"));
      }
      if (path === "/api/health") {
        const body = JSON.parse(result.text);
        check("health reports unavailable, not connected", body.database === "unavailable", `database=${body.database}`);
        check("health never claims ok", body.ok === false);
      }
    } catch (error) {
      check(`${path} responds within ${DEADLINE_MS}ms`, false, error instanceof Error ? error.message : String(error));
    }
  }
} finally {
  // Kill the whole process group: next spawns a next-server child that would
  // otherwise keep stdio open and prevent this harness from exiting.
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }
  child.stdout.destroy();
  child.stderr.destroy();
}

if (failures.length) {
  console.error(`\n${failures.length} check(s) failed.\n\nServer log:\n${serverLog.slice(-2000)}`);
  process.exit(1);
}
console.log("\nUnreachable-database regression passed: no infinite handshake.");
process.exit(0);
