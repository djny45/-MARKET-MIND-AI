# Vercel deployment: MARKET-MIND-AI frontend + Mercury backend

This repository contains a Vite frontend in `frontend/` and a FastAPI backend in `backend/`. Deploy them as **two Vercel projects** so the Python backend has its own runtime and secret environment.

## 1. Frontend project

1. In Vercel, import `djny45/-MARKET-MIND-AI`.
2. Set **Root Directory** to `frontend`.
3. Keep the Vite framework/build settings detected by Vercel (build command `npm run build`, output directory `dist`).
4. Deploy and copy the frontend's production URL, e.g. `https://your-frontend.vercel.app`.

## 2. Backend project

1. Import the same GitHub repository as a **second** Vercel project.
2. Set **Root Directory** to `backend`.
3. The `backend/vercel.json` and `backend/api/index.py` files route requests to the FastAPI app. Dependencies are in `backend/requirements.txt`.
4. Deploy the backend and copy its URL. Check `/docs` to confirm the FastAPI app is reachable.

## 3. Backend environment variables

In the backend Vercel project, open **Settings → Environment Variables** and set these for Production (and Preview if needed):

| Name | Value |
|---|---|
| `INCEPTION_API_KEY` | Your Inception Labs key (encrypted/sensitive) |
| `INTELLIGENCE_CORE_ENABLED` | `true` |
| `INTELLIGENCE_CORE_PROVIDER` | `mercury` |
| `INCEPTION_MODEL` | `mercury-3` |
| `FRONTEND_ORIGINS` | `https://<your-frontend-project>.vercel.app` (replace with the actual deployed frontend origin) |

For multiple allowed frontend origins, separate them with commas. Do not include URL paths or a trailing slash. Keep the API key only in the backend environment; never use a `VITE_*` variable for the secret because Vite exposes those values to browser code.

After changing environment variables, redeploy the backend.

## 4. Frontend-to-backend URL

The frontend reads `VITE_API_URL` (in `frontend/src/App.tsx` and other API-calling components). In the frontend Vercel project, set `VITE_API_URL` to the backend's HTTPS deployment origin, for example `https://your-backend.vercel.app` (no trailing slash). This is a public API base URL, not a secret. Redeploy the frontend after changing it.

## 5. MARKET-MIND-AI terminal HTML

The terminal page at `frontend/public/market-terminal.html` is served by the Vite frontend at `/market-terminal.html`. Open the page and use its **Backend Connection** panel to enter the deployed FastAPI backend origin (for example, `https://your-backend.vercel.app`), then press **CONNECT**. It checks `/api/health` and attempts to read `/api/market-data/overview`. The page remembers the backend origin in that browser's local storage. Its static market tiles and agent cards are mock/demo values, not live quotes, real performance, or active trading agents.

## 6. Frontend project settings\n\nThe `frontend/vercel.json` file adds an SPA fallback to `/index.html`, so client-side routes resolve correctly. Keep the frontend project root set to `frontend`; keep the backend project root set to `backend`.\n\n## 7. Verify

- Open the backend's `/docs` URL and confirm FastAPI responds.
- Check the backend's provider-status endpoint; it reports configuration only and does **not** prove Mercury credentials are valid or make a provider request.
- Test one research-synthesis request with non-sensitive sample data.
- Inspect Vercel Function logs for errors. Never log or print the API key.

## Security and limitations

- Mercury synthesis is an optional research-summary capability, not an order-execution or trading endpoint.
- CORS is allowlisted via `FRONTEND_ORIGINS`; do not use `*` with credentials.
- The backend may need additional persistence configuration for endpoints that write local SQLite/files. Vercel's serverless filesystem is not durable between invocations. Treat this as a deployment review item before relying on persistent task or market-data storage.
