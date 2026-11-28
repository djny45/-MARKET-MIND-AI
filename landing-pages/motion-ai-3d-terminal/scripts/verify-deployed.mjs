#!/usr/bin/env node
/**
 * Verifies that a DEPLOYED URL is serving the demo-mode build, not the old
 * "awaiting database handshake" fallback. Read-only: no deploys, no secrets.
 *
 *   node scripts/verify-deployed.mjs https://motion-ai-3d-terminal.vercel.app
 */

const base = (process.argv[2] ?? "https://motion-ai-3d-terminal.vercel.app").replace(/\/$/, "");
const failures = [];

function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(name);
}

async function main() {
  console.log(`Checking ${base}\n`);

  const home = await fetch(`${base}/`, { cache: "no-store" });
  const html = await home.text();
  check("homepage HTTP 200", home.status === 200, `status=${home.status}`);
  check("terminal shell is rendered", html.length > 100_000, `${html.length} bytes`);
  check("old boot fallback is GONE", !html.includes("awaiting database handshake"));
  check("demo banner is present", html.includes("read-only demo mode"));

  const market = await fetch(`${base}/api/market`, { cache: "no-store" });
  const body = await market.json();
  check("market endpoint HTTP 200", market.status === 200, `status=${market.status}`);
  check(
    "explicit data origin returned",
    body.dataOrigin === "demo-synthetic" || body.dataOrigin === "database-simulated",
    `origin=${body.dataOrigin}`,
  );
  check("market snapshot has instruments", Array.isArray(body.instruments) && body.instruments.length > 0);

  const health = await fetch(`${base}/api/health`, { cache: "no-store" });
  const hb = await health.json();
  check("health reports real DB state", hb.database === "connected" || hb.database === "unconfigured" || hb.database === "unavailable", `database=${hb.database}`);
  check("health never claims false success", hb.ok === (hb.database === "connected"));

  if (failures.length) {
    console.error(`\n${failures.length} check(s) failed — deployment is STALE.`);
    console.error(
      process.env.PROMOTE_HINT ??
        "Promote the latest verified commit of feature/motion-ai-3d-terminal in the Vercel dashboard, or merge PR #115 if production tracks main.",
    );
    process.exit(1);
  }
  console.log("\nDeployment is serving the fixed build.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
