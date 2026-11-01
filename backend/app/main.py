from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Literal
import hashlib
import json
from datetime import datetime, timezone
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .skill_catalog import list_skills, load_skill
from .markets import market_catalog
from .instruments import search_instruments
from .pipeline import system_capabilities
from .news import ingest_news
from . import indicators
from .performance import performance_metrics
from . import workspace
from .market_data import SyntheticFixtureAdapter, MarketDataBatch
from . import market_store
from . import watchlist
from .setup_report import build_setup_report
from .chart_research import build_chart_report
from .multi_timeframe import build_multi_timeframe_report, SUPPORTED_INTERVALS
from .deep_analysis import build_deep_analysis_report
from .research_timeline import build_research_timeline
from .csv_import import parse_historical_csv
from .historical_quality import build_historical_quality_diagnostics
from .source_comparison import compare_source_observations
from .research_export import build_research_evidence_bundle
from .research_export_compare import compare_research_exports
import json
import uuid
from fastapi.responses import Response

app = FastAPI(title="MARKET-MIND-AI API", version="0.2.0",
 description="Multi-market, evidence-first research pipeline. No brokerage execution.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
 allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class SaveWorkflowRequest(BaseModel):
 title: str = Field(min_length=1,max_length=120)
 description: str = Field(default="",max_length=500)
 nodes: list[dict[str,Any]] = Field(default_factory=list,max_length=250)
 edges: list[dict[str,Any]] = Field(default_factory=list,max_length=1000)

class WorkflowRequest(BaseModel):
 nodes: list[dict[str, Any]] = Field(default_factory=list)
 edges: list[dict[str, Any]] = Field(default_factory=list)
 inputs: dict[str, Any] = Field(default_factory=dict)
 max_workers: int = Field(default=1, ge=1, le=16)
 max_retries: int = Field(default=0, ge=0, le=3)
 skill_ids: list[str] = Field(default_factory=list, max_length=10)

class IndicatorRequest(BaseModel):
 values: list[float] = Field(min_length=2)
 period: int = Field(default=14, ge=1, le=10000)

class WatchlistRequest(BaseModel):
 symbol: str = Field(min_length=1, max_length=32)


class HistoricalCSVImportRequest(BaseModel):
 csv_text: str = Field(min_length=1, max_length=2_000_000)
 symbol: str = Field(min_length=1, max_length=32)
 interval: str = Field(min_length=1, max_length=16)
 source: str = Field(min_length=1, max_length=80)


class SetupReportRequest(BaseModel):
 symbol: str = Field(min_length=1, max_length=32)
 direction: Literal["long", "short"]
 entry: float = Field(gt=0)
 stop: float = Field(gt=0)
 target: float = Field(gt=0)

@app.get("/api/health")
def health():
 return {"status":"ok","service":"market-mind-ai","mode":"research-only",
  "paper_trading":False,"broker_execution":False}

@app.get("/api/watchlist")
def get_watchlist(limit: int = 100):
 """List saved instrument references for the local research workspace."""
 if limit < 1 or limit > 500:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
 return watchlist.list_symbols(limit)


@app.post("/api/watchlist")
def add_watchlist_symbol(request: WatchlistRequest):
 """Add an instrument reference to the local watchlist."""
 try:
  return watchlist.add_symbol(request.symbol)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/watchlist/{symbol}")
def delete_watchlist_symbol(symbol: str):
 """Remove an instrument reference from the local watchlist."""
 try:
  deleted = watchlist.remove_symbol(symbol)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 if not deleted:
  raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
 return {"deleted": True, "symbol": symbol.strip().upper()}


@app.get("/api/audit/events")
def audit_events(symbol: str | None = None, interval: str | None = None, limit: int = 100):
 """List recent market-data ingestion audit events."""
 if symbol is not None and (not symbol.strip() or len(symbol) > 32):
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval is not None and (not interval.strip() or interval not in SUPPORTED_INTERVALS):
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 500:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
 return market_store.get_audit_events(symbol, interval, limit)


@app.get("/api/market-data/overview")
def market_data_overview(limit: int = 200):
 """Summarize locally stored instrument and timeframe coverage."""
 if limit < 1 or limit > 500:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
 return market_store.get_market_overview(limit)


@app.get("/api/market-data/lineage")
def market_data_lineage(symbol: str, interval: str = "1h", limit: int = 5000):
 """Summarize stored observations by source and status."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
 return market_store.get_data_lineage(symbol, interval, limit)


@app.get("/api/ready")
def readiness():
 """Report whether required local storage is reachable and initialized."""
 database = market_store.database_readiness()
 ready = database["status"] == "ready"
 result = {
  "status": "ready" if ready else "not_ready",
  "service": "market-mind-ai",
  "checks": {"database": database},
  "execution": {"paper_trading": False, "broker_execution": False},
 }
 if not ready:
  raise HTTPException(status_code=503, detail={
   "status": "not_ready", "checks": {"database": database},
  })
 return result


@app.get("/api/providers/status")
def provider_status():
 """Describe implemented provider availability without implying live connectivity."""
 return {
  "status": "no_live_provider_configured",
  "live_providers": [],
  "available_adapters": [{
   "name": SyntheticFixtureAdapter.name,
   "status": "available",
   "data_status": "synthetic",
   "purpose": "development and integration testing only",
  }],
  "market_data_note": "No live or delayed market-data provider is currently configured.",
 }


@app.get("/api/nodes")
def nodes():
 return {"nodes":list(NODE_TYPES.values())}

@app.get("/api/workers")
def workers(department: str | None = None, limit: int = 550):
 items=list_workers()
 if department: items=[w for w in items if w["department"]==department]
 return {"count":len(items[:max(1,min(limit,550))]),"workers":items[:max(1,min(limit,550))]}


@app.get("/api/skills")
def skills():
 """List the allowlisted research playbooks available to worker profiles."""
 return {"count": len(list_skills()), "skills": list_skills(),
         "execution": {"paper_trading": False, "broker_execution": False}}


@app.get("/api/skills/{skill_id}")
def skill_detail(skill_id: str):
 """Load one allowlisted research playbook; unknown or broker skills are rejected."""
 try:
  return load_skill(skill_id)
 except KeyError as exc:
  raise HTTPException(status_code=404, detail="Research skill not found") from exc
 except FileNotFoundError as exc:
  raise HTTPException(status_code=404, detail="Research skill file is unavailable") from exc

@app.get("/api/markets")
def markets():
 return market_catalog()

@app.get("/api/system/capabilities")
def capabilities():
 return system_capabilities()

@app.get("/api/instruments")
def instruments(q: str = "", market: str | None = None, limit: int = 30):
 return search_instruments(q, market, limit)

@app.get("/api/news")
async def news_feed():
 return await ingest_news()

@app.post("/api/news/ingest")
async def news():
 result=await ingest_news()
 return result

@app.post("/api/indicators")
def calculate(request: IndicatorRequest):
 try:
  values=request.values; p=request.period
  return {"sma":indicators.sma(values,p),"ema":indicators.ema(values,p),
   "rsi":indicators.rsi(values,p),"macd":indicators.macd(values),
   "bollinger":indicators.bollinger(values,p),
   "realized_volatility":indicators.realized_volatility(values)}
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc

class PerformanceRequest(BaseModel):
 values: list[float] = Field(min_length=3)
 benchmark: list[float] | None = None
 periods_per_year: float | None = Field(default=None, gt=0)
 risk_free_rate: float = 0.0

@app.get("/api/research/timeframes")
def research_timeframes(
 symbol: str,
 intervals: str = "15m,1h,4h,1d",
 limit: int = 500,
):
 """Optional cross-timeframe descriptive comparison over stored bars."""
 requested = [item.strip() for item in intervals.split(",") if item.strip()]
 if not requested or len(requested) > 4 or any(item not in SUPPORTED_INTERVALS for item in requested):
  raise HTTPException(status_code=400, detail="intervals must be a comma-separated subset of 15m,1h,4h,1d")
 histories = {item: market_store.get_bars(symbol, item, limit) for item in requested}
 try:
  return build_multi_timeframe_report(symbol, histories)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/research/setup")
def research_setup(request: SetupReportRequest):
 """Calculate user-defined scenario geometry; never emits an execution instruction."""
 try:
  return build_setup_report(request.symbol, request.direction, request.entry, request.stop, request.target)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/analytics/performance")
def analyze_performance(request: PerformanceRequest):
 try:
  return performance_metrics(request.values, request.benchmark, request.periods_per_year, request.risk_free_rate)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/workspaces")
def list_saved_workflows(limit: int = 50):
 return {"workflows":workspace.list_workflows(limit)}

@app.get("/api/workspaces/{workflow_id}")
def get_saved_workflow(workflow_id: str):
 result=workspace.get_workflow(workflow_id)
 if result is None: raise HTTPException(status_code=404,detail="Workflow not found")
 return result

@app.post("/api/workspaces")
def save_named_workflow(request: SaveWorkflowRequest):
 try:
  return workspace.save_workflow(request.title,request.description,request.nodes,request.edges)
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.put("/api/workspaces/{workflow_id}")
def update_named_workflow(workflow_id: str, request: SaveWorkflowRequest):
 if workspace.get_workflow(workflow_id) is None:
  raise HTTPException(status_code=404,detail="Workflow not found")
 try:
  return workspace.save_workflow(request.title,request.description,request.nodes,request.edges,workflow_id)
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.delete("/api/workspaces/{workflow_id}")
def remove_named_workflow(workflow_id: str):
 if not workspace.delete_workflow(workflow_id):
  raise HTTPException(status_code=404,detail="Workflow not found")
 return {"deleted":True,"id":workflow_id}


@app.get("/api/market-data/sample")
async def sample_market_data(symbol: str = "BTCUSD", interval: str = "1d", limit: int = 5):
 """Return a clearly labelled synthetic fixture for UI and integration testing."""
 try:
  batch = await SyntheticFixtureAdapter().get_bars(symbol, interval, limit)
  return batch.model_dump(mode="json")
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/market-data/store")
def store_market_data(batch: MarketDataBatch):
 """Persist normalized observations while retaining source and status metadata."""
 return market_store.store_batch(batch)

@app.post("/api/market-data/import-csv")
def import_historical_csv(request: HistoricalCSVImportRequest):
 """Validate and store a user-supplied historical OHLCV CSV; no live data or execution."""
 try:
  batch = parse_historical_csv(
   request.csv_text, request.symbol, request.interval, request.source
  )
  result = market_store.store_batch(batch)
  return {
   "imported": True,
   **result,
   "warnings": batch.warnings,
   "status": batch.status.value,
  }
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/chart")
def research_chart(symbol: str, interval: str = "1d", limit: int = 500):
 """Analyze stored OHLCV descriptively; no signal generation or execution."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 history = market_store.get_bars(symbol, interval, limit)
 try:
  return build_chart_report(history)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/market-data/history")
def market_data_history(symbol: str, interval: str = "1d", limit: int = 500):
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if not interval.strip() or len(interval) > 16:
  raise HTTPException(status_code=400, detail="interval must contain 1 to 16 characters")
 return market_store.get_bars(symbol, interval, limit)


@app.get("/api/research/export")
def export_research_evidence(symbol: str, interval: str = "1h", limit: int = 500):
 """Download a JSON evidence bundle with observations, provenance and diagnostics."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
 history = market_store.get_bars(symbol, interval, limit)
 bundle = build_research_evidence_bundle(symbol, interval, history)
 content = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False)
 filename = f"{symbol.strip().upper()}-{interval}-research-evidence.json"
 return Response(content=content, media_type="application/json",
  headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/research/compare-exports")
def compare_export_bundles(payload: dict[str, Any]):
 """Compare two compatible historical evidence exports supplied by the caller."""
 before = payload.get("before")
 after = payload.get("after")
 try:
  return compare_research_exports(before, after)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/research/source-comparison")
def research_source_comparison(symbol: str, interval: str = "1h", limit: int = 500):
 """Compare stored historical observations from distinct sources at exact UTC instants."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
 return compare_source_observations(market_store.get_bars(symbol, interval, limit))


@app.get("/api/research/data-quality")
def research_data_quality(symbol: str, interval: str = "1h", limit: int = 500):
 """Return elapsed-time and robust outlier diagnostics for stored history."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
 history = market_store.get_bars(symbol, interval, limit)
 return build_historical_quality_diagnostics(history)


@app.get("/api/research/timeline")
def research_timeline(symbol: str, interval: str = "1h", limit: int = 200):
 """Return timestamped descriptive observations from stored OHLCV bars."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 1000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
 history = market_store.get_bars(symbol, interval, min(limit, 5000))
 try:
  return build_research_timeline(history, limit)
 except (KeyError, TypeError, ValueError) as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/deep")
def research_deep(
 symbol: str,
 intervals: str = "15m,1h,4h,1d",
 limit: int = 500,
 compare_symbols: str = "",
 breadth_symbols: str = "",
):
 """Return integrated descriptive research and dashboard from stored bars."""
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 requested = [item.strip() for item in intervals.split(",") if item.strip()]
 if not requested or len(requested) > 4 or any(item not in SUPPORTED_INTERVALS for item in requested):
  raise HTTPException(status_code=400, detail="intervals must be a comma-separated subset of 15m,1h,4h,1d")
 safe_limit = max(1, min(limit, 5000))
 histories = {item: market_store.get_bars(symbol, item, safe_limit) for item in requested}
 primary_interval = requested[0]
 multi_report = None
 if len(requested) > 1:
  try:
   multi_report = build_multi_timeframe_report(symbol, histories)
  except ValueError:
   multi_report = None
 correlation_histories = None
 if compare_symbols.strip():
  names = sorted({symbol.strip().upper()} | {item.strip().upper() for item in compare_symbols.split(",") if item.strip()})
  if len(names) < 2 or len(names) > 12:
   raise HTTPException(status_code=400, detail="compare_symbols must add at least one symbol; maximum 12 total")
  correlation_histories = {name: market_store.get_bars(name, primary_interval, safe_limit) for name in names}
 breadth_histories = None
 if breadth_symbols.strip():
  names = sorted({symbol.strip().upper()} | {item.strip().upper() for item in breadth_symbols.split(",") if item.strip()})
  if len(names) < 2 or len(names) > 30:
   raise HTTPException(status_code=400, detail="breadth_symbols must add at least one symbol; maximum 30 total")
  breadth_histories = {name: market_store.get_bars(name, primary_interval, safe_limit) for name in names}
 try:
  return build_deep_analysis_report(symbol, histories, multi_report, correlation_histories, breadth_histories)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

def _workflow_request_fingerprint(request_payload: dict) -> str:
 return hashlib.sha256(
  json.dumps(request_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
 ).hexdigest()


def _validate_checkpoint_integrity(request_payload: dict, checkpoint: dict, known_ids: set[str]) -> None:
 expected = _workflow_request_fingerprint(request_payload)
 if checkpoint.get("request_fingerprint") != expected:
  raise HTTPException(status_code=409, detail="Checkpoint does not match the original workflow request.")
 completed_ids = set(checkpoint.get("completed_node_ids", []))
 if not completed_ids.issubset(known_ids):
  raise HTTPException(status_code=409, detail="Checkpoint contains nodes not present in the saved workflow.")
 results = checkpoint.get("results", {})
 tasks = checkpoint.get("tasks", {})
 if any(node_id not in results or tasks.get(node_id, {}).get("status") != "completed" for node_id in completed_ids):
  raise HTTPException(status_code=409, detail="Checkpoint is incomplete or internally inconsistent.")


def _execute_and_persist(request: WorkflowRequest, parent_run_id: str | None = None, initial_checkpoint: dict | None = None):
 try:
  if len(set(request.skill_ids)) != len(request.skill_ids):
   raise HTTPException(status_code=400, detail="skill_ids must not contain duplicates")
  loaded_skills = []
  for skill_id in request.skill_ids:
   try:
    loaded_skills.append(load_skill(skill_id))
   except KeyError as exc:
    raise HTTPException(status_code=400, detail=f"Unsupported research skill: {skill_id}") from exc
   except FileNotFoundError as exc:
    raise HTTPException(status_code=503, detail=f"Research skill unavailable: {skill_id}") from exc
  request_payload = request.model_dump()
  fingerprint = _workflow_request_fingerprint(request_payload)
  if initial_checkpoint:
   known_ids = {str(node.get("id", "")) for node in request.nodes}
   _validate_checkpoint_integrity(request_payload, initial_checkpoint, known_ids)
  run_id = str(uuid.uuid4())
  record = workspace.create_execution(run_id, request_payload, parent_run_id)
  def persist_checkpoint(snapshot):
   snapshot["request_fingerprint"] = fingerprint
   snapshot["checkpoint_schema_version"] = 1
   snapshot["checkpointed_at"] = datetime.now(timezone.utc).isoformat()
   workspace.update_execution_checkpoint(run_id, snapshot, "running")
  result = execute_workflow(
   request.nodes, request.edges, request.inputs,
   request.max_workers, request.max_retries, persist_checkpoint, initial_checkpoint,
  )
  result["skill_context"] = loaded_skills
  result["skill_context_mode"] = "research_and_paper_only"
  record = workspace.update_execution_checkpoint(
   run_id,
   {"completed_node_ids":[task["node_id"] for task in result["tasks"] if task["status"]=="completed"],
    "results":result["results"],"tasks":{task["node_id"]:task for task in result["tasks"]},
    "completed_layers":len(result["execution_layers"]),
    "request_fingerprint":fingerprint,"checkpoint_schema_version":1,
    "checkpointed_at":datetime.now(timezone.utc).isoformat()},
   result["status"], result,
  )
  result["run_id"] = run_id
  result["run_record"] = record
  return result
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc
 except HTTPException:
  raise
 except Exception as exc:
  raise HTTPException(status_code=500,detail=f"Workflow failed: {exc}") from exc


@app.post("/api/workflows/execute")
def run_workflow(request: WorkflowRequest):
 return _execute_and_persist(request)


@app.get("/api/workflows/runs")
def list_workflow_runs(limit: int = 50):
 if limit < 1 or limit > 100:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
 return {"runs": workspace.list_executions(limit)}


@app.get("/api/workflows/runs/{run_id}")
def get_workflow_run(run_id: str):
 record = workspace.get_execution(run_id)
 if record is None:
  raise HTTPException(status_code=404, detail="Workflow run not found")
 return record


@app.post("/api/workflows/runs/{run_id}/resume")
def resume_workflow_run(run_id: str):
 record = workspace.get_execution(run_id)
 if record is None:
  raise HTTPException(status_code=404, detail="Workflow run not found")
 request = WorkflowRequest(**record["request"])
 checkpoint = record.get("checkpoint") or {}
 completed_ids = checkpoint.get("completed_node_ids", [])
 checkpoint_tasks = checkpoint.get("tasks", {})
 restored_count = sum(
  1 for node_id in completed_ids
  if checkpoint_tasks.get(node_id, {}).get("status") == "completed"
  and node_id in checkpoint.get("results", {})
 )
 checkpoint_age_seconds = None
 checkpoint_timestamp = checkpoint.get("checkpointed_at") or record.get("updated_at")
 if checkpoint_timestamp:
  try:
   parsed = datetime.fromisoformat(checkpoint_timestamp.replace("Z", "+00:00"))
   if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
   checkpoint_age_seconds = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())
  except (TypeError, ValueError):
   checkpoint_age_seconds = None
 replay = _execute_and_persist(request, parent_run_id=run_id, initial_checkpoint=checkpoint)
 replay["resume_mode"] = "checkpoint_resume"
 replay["recovery"] = {
  "source_run_id": run_id,
  "restored_task_count": restored_count,
  "checkpoint_age_seconds": round(checkpoint_age_seconds, 3) if checkpoint_age_seconds is not None else None,
  "checkpoint_schema_version": checkpoint.get("checkpoint_schema_version"),
  "checkpoint_completed_layers": checkpoint.get("completed_layers", 0),
 }
 replay["resume_note"] = "Completed nodes from the last durable layer checkpoint were restored; incomplete nodes were scheduled again."
 return replay
