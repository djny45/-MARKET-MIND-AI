# MARKET-MIND-AI

**An open-source, node-based global market intelligence and quantitative research terminal.**

MARKET-MIND-AI is designed around a ComfyUI-style visual graph: analytical workers are modular nodes with typed inputs and outputs, connected into directed research workflows. A central intelligence layer coordinates analysis while the graph engine handles deterministic computations and traceable data flow.

## Current application foundation

- React + TypeScript + React Flow visual node editor.
- Dark terminal-style interface with node library, worker catalogue, graph connections, execution inspector, and editable sample data.
- FastAPI backend with a directed acyclic graph (DAG) execution engine.
- 550 generated specialist worker profiles across 20 research departments. These are catalogue templates, not 550 completed autonomous agents or separate AI models.
- Implemented graph nodes: market input, data-quality validation, simple moving average, returns, realized volatility, and descriptive research summary.
- Cycle detection, unsupported-node rejection, finite-number validation, and API health endpoint.
- Docker Compose development environment.

## Run locally

```bash
docker compose up --build
```

Open the terminal at http://localhost:5173 and API documentation at http://localhost:8000/docs.

See [Development Guide](docs/DEVELOPMENT.md), [Architecture](docs/ARCHITECTURE.md), and [Roadmap](docs/ROADMAP.md).

## API endpoints

- `GET /api/health`
- `GET /api/nodes`
- `GET /api/workers?limit=550`
- `POST /api/workflows/execute`

## Planned direction

Global market data adapters, live and delayed feed labelling, advanced charting, multi-asset screeners, fundamentals, macroeconomic intelligence, document/news retrieval, additional analytical workers, persistent workspaces, and production-grade observability.

## Product boundaries

This is a research and information platform. It does not include paper trading, broker credentials, order routing, automated trade execution, or personalized investment instructions. The current sample workflow uses user-entered demo values; live market feeds are not implemented yet.

All data connectors must respect provider terms, licences, attribution, rate limits, and redistribution rights. Bloomberg branding, proprietary datasets, and proprietary terminal content are not copied or redistributed.
