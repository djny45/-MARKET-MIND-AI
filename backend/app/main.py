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

@app.post("/api/workflows/execute")
def run_workflow(request: WorkflowRequest):
 try:
  return execute_workflow(request.nodes,request.edges,request.inputs)
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc
 except Exception as exc:
  raise HTTPException(status_code=500,detail=f"Workflow failed: {exc}") from exc
