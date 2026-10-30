# Running MARKET-MIND-AI

## Requirements
- Docker and Docker Compose, or Python 3.11+ and Node.js 20+.

## Start with Docker Compose
From the repository root:

```bash
docker compose up --build
```

Open the terminal at http://localhost:5173 and API documentation at http://localhost:8000/docs.

## Run services without Docker

Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend in a second terminal:
```bash
cd frontend
npm install
npm run dev
```

## Use the graph
1. The default canvas shows a sample market-research DAG.
2. Edit the comma-separated sample close-price series in the bottom data bar.
3. Add nodes from the node library or switch to Workers and search the worker catalogue.
4. Connect output handles to input handles.
5. Select **Run Workflow** and inspect the execution output.

The initial engine implements market input, data-quality checks, simple moving average, returns, realized volatility, and descriptive research-summary nodes. The other worker profiles are catalogue templates and are not yet executable. The graph runner rejects cycles and unsupported node types.

## API
- GET /api/health
- GET /api/nodes
- GET /api/workers?limit=550
- POST /api/workflows/execute

## Current limitations
- Demo values are user-provided sample data, not a live market feed.
- Provider adapters, authentication, persistent workspaces, real-time streaming, advanced charting, and full worker implementations remain future milestones.
- No broker connection, order routing, automated trading, or paper-trading functionality is included.

## Instrument discovery, chart and news workspace

The header instrument finder queries `GET /api/instruments?q=<text>`. Results are reference metadata (symbol, name, market class, venue and currency), not quotes or a complete global security master.

The chart uses the user-entered sample close series and Lightweight Charts. Its time axis is illustrative and the panel is explicitly labelled **SAMPLE INPUT DATA — NOT A LIVE QUOTE**. It must not be interpreted as historical exchange data.

Select **NEWS** in the sidebar and fetch the configured official RSS feeds. The panel displays publisher headlines, publication timestamps and links. A failed feed is reported rather than silently treated as a complete news result. Publisher availability and terms must be verified for deployment.

## Saved research workspaces

Use the terminal's workspace name field and **SAVE GRAPH** to persist the current React Flow nodes and edges. Choose an item from **LOAD WORKSPACE** to restore it. The API stores graph JSON in SQLite.

Endpoints:
- `GET /api/workspaces` — list saved graphs.
- `POST /api/workspaces` — create a saved graph.
- `GET /api/workspaces/{id}` — load one graph.
- `PUT /api/workspaces/{id}` — update an existing graph.
- `DELETE /api/workspaces/{id}` — delete a graph.

Docker Compose mounts a named volume at `/data` and sets `MARKET_MIND_DB=/data/market_mind.db`, so saved graphs persist across container recreation. The workspace API is currently a single-user development feature; add authentication and per-user authorization before exposing it to a public network.
