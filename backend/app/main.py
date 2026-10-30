from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .markets import market_catalog
from .instruments import search_instruments
from .pipeline import system_capabilities
from .news import ingest_news
from . import indicators
from .performance import performance_metrics

app = FastAPI(title="MARKET-MIND-AI API", version="0.2.0",
 description="Multi-market, evidence-first research pipeline. No brokerage execution.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
 allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class WorkflowRequest(BaseModel):
 nodes: list[dict[str, Any]] = Field(default_factory=list)
 edges: list[dict[str, Any]] = Field(default_factory=list)
 inputs: dict[str, Any] = Field(default_factory=dict)

class IndicatorRequest(BaseModel):
 values: list[float] = Field(min_length=2)
 period: int = Field(default=14, ge=1, le=10000)

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

@app.post("/api/analytics/performance")
def analyze_performance(request: PerformanceRequest):
 try:
  return performance_metrics(request.values, request.benchmark, request.periods_per_year, request.risk_free_rate)
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
