# Vercel-free frontend deployment with GitHub Pages

This workflow publishes the **static React/Vite frontend** using GitHub Actions and GitHub Pages. It does not host FastAPI, SQLite, or any background worker.

## One-time GitHub setup

1. Open the repository's **Settings → Pages**.
2. Set the Pages build/deployment source to **GitHub Actions**.
3. Confirm the repository permits GitHub Actions deployments.

## Prepare the backend before deployment

The frontend calls the API URL baked into the Vite build. Before deploying, provide an HTTPS backend URL that is secured for browser access.

**Security gate:** the current FastAPI application does not implement user authentication or per-user authorization. Do not expose it to the public internet or connect a public Pages site to an openly accessible instance. Add authentication, authorization, TLS ingress, request limits, and a security review first. Configure the backend's `FRONTEND_ORIGINS` allowlist to include the exact Pages origin; do not use wildcard CORS.

The workflow input is a URL, not a secret. Never place API keys, passwords, or tokens in that field or in frontend environment variables—anything embedded in a static frontend is public.

## Deploy

1. Open **Actions → Deploy frontend to GitHub Pages (Vercel-free)**.
2. Select **Run workflow**.
3. Enter the secured backend's HTTPS base URL, for example `https://api.example.com` (replace with your real URL).
4. Run the workflow and wait for the build and Pages deployment jobs to finish.
5. Open the published Pages URL shown in the deployment job.

The workflow uses the repository name as Vite's Pages base path. Local Vite development and self-hosted root deployments keep the default `/` base path.

## Local development

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

For local development, the frontend defaults to `http://localhost:8000`. Configure the backend's `FRONTEND_ORIGINS` to include `http://localhost:5173`.

## Scope

- GitHub Pages hosts static frontend files only.
- FastAPI, SQLite, backups, and worker processes must run on a separate host.
- This is a deployment path—not evidence of a successful live deployment or a backend security audit.
- Market data remains subject to the app's existing research-only/synthetic-data limits; no broker execution is enabled.
