#!/usr/bin/env node
/**
 * Verification harness for the terminal's database-ready / demo fallback.
 *
 * Requires a running server (next start). Use BASE_URL to point at it.
 * Tests the real HTTP surface; no credentials are read or printed.
 *
 *   npm run start -- -p 3123 &
 *   node scripts/verify-terminal.mjs
 */

const base = process.env.BASE_URL ?? "http://127.0.0.1:3123";
const failures = [];

function check(name, condition, detail = "") {
  if (condition) {
    console.log(`PASS  ${name}`);
  } else {
    failures.push(`${name}${detail ? `: ${detail}` : ""}`);
    console.error(`FAIL  ${name}${detail ? `: ${detail}` : ""}`);
  }
}

async function json(path, init) {
  const response = await fetch(`${base}${path}`, init);
  let body;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return { status: response.status, body };
}

async function main() {
  // 1. Homepage must render with real content, not the blank boot fallback.
  const home = await fetch(`${base}/`);
  const html = await home.text();
  check("homepage HTTP 200", home.status === 200, `status=${home.status}`);
  check("homepage renders terminal shell", html.includes("terminal") || html.includes("market mind ai"));
  check("homepage has no boot-only fallback", !html.includes("awaiting database handshake"));

  // 2. Market snapshot: demo origin must be explicit when DB is unavailable.
  const market = await json("/api/market");
  check("market endpoint HTTP 200", market.status === 200, `status=${market.status}`);
  const origin = market.body?.dataOrigin;
  check(
    "market data origin is explicit",
    origin === "demo-synthetic" || origin === "database-simulated",
    `origin=${origin}`,
  );
  check("market snapshot has instruments", Array.isArray(market.body?.instruments) && market.body.instruments.length > 0);
  check("market snapshot has 550 agents", market.body?.agents?.total === 550, `total=${market.body?.agents?.total}`);
  check("market snapshot has signals", Array.isArray(market.body?.signals) && market.body.signals.length > 0);
  if (origin === "demo-synthetic") {
    check("demo mode is flagged in API", market.body?.demo === true, `demo=${market.body?.demo}`);
    check("demo banner is rendered", html.includes("read-only demo mode"));
  }

  // 3. Health must never falsely claim a connection.
  const health = await json("/api/health");
  if (health.body?.database === "connected") {
    check("connected health reports no demo mode", health.body.demoMode === false);
  } else {
    check("unconfigured/unavailable health is 503", health.status === 503, `status=${health.status}`);
    check("health reports demo mode", health.body?.demoMode === true);
    check("health includes remediation", typeof health.body?.remediation === "string");
    check("health does not claim ok", health.body?.ok === false);
  }

  // 4. Other API contracts stay usable in demo mode.
  const agents = await json("/api/agents?page=1&perPage=6");
  check("agents endpoint HTTP 200", agents.status === 200);
  check("agents payload labels origin", !!agents.body?.dataOrigin);
  check("agents payload has items", Array.isArray(agents.body?.items) && agents.body.items.length > 0);

  const detail = await json("/api/agents/1");
  check("agent detail HTTP 200", detail.status === 200);
  check("agent detail labels origin", !!detail.body?.dataOrigin);

  const signals = await json("/api/signals?limit=5");
  check("signals endpoint HTTP 200", signals.status === 200);
  check("signals payload labels origin", !!signals.body?.dataOrigin);

  const scan = await json("/api/scan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ count: 3 }),
  });
  check("scan endpoint HTTP 200", scan.status === 200);
  check("scan payload labels origin", !!scan.body?.dataOrigin);

  // 5. Optional backend probe must remain informational (never an error).
  const backend = await json("/api/backend");
  check("backend probe HTTP 200", backend.status === 200);

  if (failures.length > 0) {
    console.error(`\n${failures.length} check(s) failed.`);
    process.exit(1);
  }
  console.log("\nAll terminal checks passed.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
