from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Literal
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .markets import market_catalog
from .instruments import search_instruments
from .pipeline import system_capabilities
from .news import ingest_news
from . import indicators
from .performance import performance_metrics
from . import workspace
from .market_data import SyntheticFixtureAdapter, MarketDataBatch
from . import market_store
from .setup_report import build_setup_report
from .chart_research import build_chart_report
from .multi_timeframe import build_multi_timeframe_report, SUPPORTED_INTERVALS
from .deep_analysis import build_deep_analysis_report
from .research_timeline import build_research_timeline
from .csv_import import parse_historical_csv
from .historical_quality import build_historical_quality_diagnostics

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

class IndicatorRequest(BaseModel):
 values: list[float] = Field(min_length=2)
 period: int = Field(default=14, ge=1, le=10000)

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

@app.get("/api/nodes")
def nodes():
 return {"nodes":list(NODE_TYPES.values())}

@app.get("/api/workers")
def workers(department: str | None = None, limit: int = 550):
 items=list_workers()
 if department: items=[w for w in items if w["department"]==department]
 return {"count":len(items[:max(1,min(limit,550))]),"workers":items[:max(1,min(limit,550))]}

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

@app.post("/api/workflows/execute")
def run_workflow(request: WorkflowRequest):
 try:
  return execute_workflow(request.nodes,request.edges,request.inputs)
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc
 except Exception as exc:
  raise HTTPException(status_code=500,detail=f"Workflow failed: {exc}") from exc
