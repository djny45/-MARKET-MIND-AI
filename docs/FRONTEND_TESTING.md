# Frontend testing (updated 2026-11-23)

React 18 + TypeScript with the existing custom esbuild build. No Vite migration,
no live-trading, wallet or order-routing code.

## Commands and verified results on this audit branch

| Command | Result |
| --- | --- |
| `npm test` (node:test, `tests/*.test.mjs`) | **10/10 pass** |
| `npx -y node@22 ./node_modules/vitest/vitest.mjs run` | **127/127 pass, 21 files** |
| `npx -y node@22 ./node_modules/typescript/bin/tsc -p tsconfig.test.json --noEmit` | **clean** |
| `npm run build` | **PASS — tsc + esbuild bundle** |
| `npm audit --omit=dev --audit-level=high` | **0 vulnerabilities** |

Vitest 5.1.1 requires Node >=22.12.0 (declared in `package.json` `engines`);
the local default Node is 20.8.1, so Node 22 is invoked explicitly. CI uses
Node 22. `frontend/package-lock.json` is tracked and consistent with
`package.json`.

## Added in this audit

| Feature | Source | Tests |
| --- | --- | --- |
| Authentication UI | `src/AuthPanel.tsx` | `tests/ui/auth-panel.test.tsx` (disabled/anonymous/login success+failure/expired/logout with CSRF cookie) |
| Role-aware navigation | `src/App.tsx` | `tests/ui/app.general-fixes.test.tsx` (viewer hides privileged tabs; operator sees them) |
| Observation screener | `src/CoverageTools.tsx` | `tests/ui/coverage-tools.test.tsx` (symbol/timeframe/min-count filters, loading/error/empty, load action) |
| Coverage heatmap | `src/CoverageTools.tsx` | `tests/ui/coverage-tools.test.tsx` (symbol x timeframe grid, intensity legend, labelled cells, empty state) |
| Help button | `src/App.tsx` | `tests/ui/app.general-fixes.test.tsx` (dialog opens/closes, aria-modal) |
| News HTTP failures | `src/App.tsx` | `tests/ui/app.news.test.tsx` (non-2xx detail surfaced via `role="alert"`) |
| Watchlist refresh busy/error | `src/App.tsx` | `tests/ui/app.general-fixes.test.tsx` (busy label, error from 503 detail) |

`tests/ui/coverage-gaps.test.ts` no longer asserts that auth/screener/heatmap
are absent; it now guards that the auth UI uses only `/api/auth/*` session
endpoints and stores no tokens in web storage, and that the coverage tools
label stored observations as historical and never as price/liquidity/activity.

The previous documented-gap test for non-2xx news responses was replaced with a
real assertion rather than deleted. No existing assertion was weakened.

## Remaining limitations

- `jsdom` cannot evaluate CSS media queries; responsive tests check declarations
  and DOM availability, not computed layout. A real-browser check is not
  configured (no Playwright/Cypress dependency).
- Canvas drag-to-connect is replaced by a test double; real handlers are still
  invoked directly.
- The frontend role gating is advisory; server-side authorization remains the
  authoritative control and is disabled unless `MARKET_MIND_USER_AUTH` is set.
- `color-contrast` is disabled in axe scans because jsdom has no CSS.
