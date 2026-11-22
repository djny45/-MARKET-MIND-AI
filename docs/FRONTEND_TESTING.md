# Frontend testing (Phase 2)

The frontend keeps its React 18 + TypeScript architecture and its custom esbuild
build (`frontend/scripts/build.mjs`). **No Vite migration and no live-trading,
wallet or order-routing code was added.** A Vitest/jsdom UI suite was added
alongside the original `node:test` suite; the two suites run independently.

## Commands

Run from `frontend/`:

| Command | What it does | Result on `main` (2026-11-22) |
| --- | --- | --- |
| `npm test` | Original node:test suite, `tests/*.test.mjs` | 10/10 pass |
| `npm run test:ui` | New Vitest/jsdom React suite, `tests/ui/**/*.test.tsx` | 99/99 pass across 16 files |
| `npm run test:all` | Both suites sequentially | both pass |
| `npm run test:ui:watch` | Vitest watch mode (local dev) | n/a |
| `npm run typecheck:test` | Typecheck app + UI suite via `tsconfig.test.json` | clean |
| `npm run build` | Existing `tsc -p tsconfig.json` + esbuild bundle | passes |

`npm run test:ui` is deliberately scoped by `vitest.config.ts` to
`tests/ui/**/*.test.{ts,tsx}` so it never re-runs the `node:test` `.mjs` files.

**Runtime requirement:** Vitest 5.1.1 (upgraded from 2.1.9 after CI's
dependency audit found critical advisories in `tinypool`/`vite`/`@vitest/mocker`)
requires Node.js **>=22.12.0**, declared in `frontend/package.json` `engines`.
CI already uses Node 22. The original `npm test` and the production build still
run on the repository's older local Node, but the UI suite must be run with
Node 22+ (e.g. `npx -y node@22 ./node_modules/vitest/vitest.mjs run`).
`npm audit --audit-level=high` is clean with this dependency set.

## Stack and why Doubles Are Used

Dev dependencies added: `vitest`, `jsdom`, `@testing-library/react`,
`@testing-library/dom`, `@testing-library/user-event`, `@testing-library/jest-dom`,
`jest-axe`, `@types/jest-axe`, `@types/node`.

`vitest.config.ts` aliases two libraries **in tests only**:

- `@xyflow/react` → `tests/ui/mocks/xyflow.tsx`. The real flow renderer needs
  canvas/layout APIs jsdom lacks. The double renders the real node data as DOM,
  so node counts, labels and `onNodeClick` are still exercised against the real
  handlers. A test-only `__flowTest.connect()` exercises `onConnect` (a canvas
  gesture that cannot be simulated in jsdom).
- `lightweight-charts` → `tests/ui/mocks/lightweight-charts.ts`. Spies on
  `createChart`, `addSeries`, `setData` and marker wiring let the tests assert
  that `PriceChart` passes the correct bars/values/cluster overlay.

`tests/ui/setup.ts` supplies jsdom gaps: `ResizeObserver`, `matchMedia`,
`Blob.prototype.text`/`File` text reading, object URLs and RTL cleanup.

API integration uses `vi.stubGlobal('fetch', …)` through
`tests/ui/helpers.tsx#mockFetch`, which routes by `METHOD /path`, records every
call (URL + method + body), and supplies fixtures for every endpoint the app
calls on mount. Per-test override routes let tests force success, 4xx/5xx,
rejections and deferred (loading-state) responses.

## Coverage matrix

| Area | File(s) | What is asserted |
| --- | --- | --- |
| Harness | `smoke.test.tsx` | Real `App` renders with mocked fetch |
| Dashboard / market overview | `app.overview.test.tsx` | Cards, API status, module-link navigation, refresh + loading, offline state, coverage rows, chart open/close, coverage errors, config dialog, toolbar controls |
| Watchlist | `app.watchlist.test.tsx` | Empty state, refresh, stored coverage, instrument search (Enter + button), add/already-saved/API error, remove (DELETE), RESEARCH navigation, busy label |
| Workers / skills / graph | `app.workers.test.tsx` | Available-skill filtering, worker search, node addition by worker and all 10 palette items, skill IDs in the real execute payload, connect handler, run busy/success/error, synthetic fixture labelling, research-only banners |
| Saved layouts | `app.workspaces.test.tsx` | Save payload, SAVING… state, workspace list refresh, load restores nodes/edges/title, save/load errors |
| Execution history | `app.runs.test.tsx` | History load/refresh, error, inspect run + recovery details, checkpoint replay POST and busy state, close details |
| News | `app.news.test.tsx` | Fetch, source-linked links, busy state, in-response source errors, network error |
| Validation | `app.validation.test.tsx` | Payload POST, valid/invalid reports, error/warning details, malformed JSON, load sample, busy state |
| Research workbench | `app.research.test.tsx` | CSV file/extension/size validation and import chain, offline benchmark (threshold, baseline limit, report, export, API error), deep research payload/report/busy/error, audit + lineage, two-file export diff, 10 MB limit, volume/liquidity calculations, cluster and timeline inspectors |
| Agent network | `agent-network.test.tsx` | Profile/core rendering, activity success/failure, node status, search/department/reset, node inspector, 20 s polling, labelled filters |
| Agent positions | `agent-position-monitor.test.tsx` | 50/60 pagination, stance assignment, summary filter, department/stance filters, tag-filtered-neutral, reset, row inspector, instrument switch |
| Learning lab | `learning-lab.test.tsx` | Overview stats/filter, request error + refresh, feedback POST payload/success/reload, API error, governance guard |
| Chart | `price-chart.test.tsx` | Manual vs stored headings, source/status metadata, chronological series data, markers, cluster overlay, no fabricated data, cleanup |
| Accessibility | `accessibility.test.tsx` | `jest-axe` scans of 7 real views + labelled controls + keyboard Enter activation |
| Responsive | `responsive-layout.test.tsx` | Media-query inventory in `style.css`, controls remain mounted at a simulated 390 px viewport |
| Coverage guards | `coverage-gaps.test.ts` | Absent features (auth/screener/heatmap/wallet) stay absent; esbuild build and node:test script unchanged |

Every interactive control exercised in these views is clicked/changed and its
effect asserted via a DOM change or a recorded fetch call. `mockFetch` records
all calls, so "a button did nothing" fails the test.

## Minimal source changes required for testability / accessibility

These are aria-label-only changes; no component behaviour, routing or data flow
was changed:

- `src/App.tsx`: `aria-label` on the help icon button, worker-search input,
  validation payload textarea, execution-inspector close button and chart
  timeframe select.
- `src/AgentPositionMonitor.tsx`: `aria-label` on the search input, department
  select and stance select.
- `src/LearningLab.tsx`: `aria-label` on the agent filter input.

## Gaps and known limitations (nothing fabricated)

1. **No authentication exists.** The app has no login/logout form, protected
   view, bearer token, session-expiry handling or auth API call. Login
   success/failure, logout, protected-view redirect and session-expiry tests
   therefore cannot be written against real components. `coverage-gaps.test.ts`
   asserts these features remain absent so that adding them requires new tests.
2. **No screener and no heatmap** component, route or endpoint exists. Same
   guard applies. "Market overview" coverage is the dashboard/coverage panel in
   `App.tsx`; "worker/skill interface" is the AGENT DIRECTORY tab; "saved
   layout" is the workspace save/load feature.
3. **Help icon button (`?`) has no handler** in the current App — it is a
   visible, labelled control with no effect. Only `aria-label` was added; wiring
   an action is a product decision and was out of scope.
4. **News non-2xx responses with `detail` are silently ignored** by
   `loadNews` (it never checks `response.ok`). A test documents this current
   behaviour; network rejections do show an error.
5. **"SELECT EXACTLY TWO JSON EXPORT FILES" guard is unreachable** from the UI
   because the compare button is disabled unless two files are selected;
   the 10 MB and malformed-file paths are covered instead.
6. **Refreshing the watchlist does not set `watchlistBusy`**, so REFRESH
   WATCHLIST has no loading state. Add/remove/overview loading states are
   covered.
7. **Real breakpoint behaviour is not verifiable in jsdom** (no layout engine);
   the suite checks the media-query declarations and DOM availability, not
   computed widths. A browser-level visual check remains a gap.
8. **Drag-to-connect and actual canvas rendering** are replaced by the flow
   double; the real handlers are invoked directly, but pointer-gesture
   integration is not covered.
9. No e2e/browser test runner or CI change was added (outside this task's scope).

## Change inventory

New: `frontend/vitest.config.ts`, `frontend/tsconfig.test.json`,
`frontend/tests/ui/**` (14 test files + setup/helpers/2 mocks), this document.
Modified: `frontend/package.json` (scripts + devDependencies),
`frontend/package-lock.json` (dependency resolution; this file was already
untracked at the start of the task), the three `src/*.tsx` files listed above.

No commits were created and nothing was pushed. `backend/`, root status reports
and workflows were not touched.
