from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .markets import market_catalog
from .pipeline import system_capabilities
from .news import ingest_news
from . import indicators

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

@app.post("/api/workflows/execute")
def run_workflow(request: WorkflowRequest):
 try:
  return execute_workflow(request.nodes,request.edges,request.inputs)
 except ValueError as exc:
  raise HTTPException(status_code=400,detail=str(exc)) from exc
 except Exception as exc:
  raise HTTPException(status_code=500,detail=f"Workflow failed: {exc}") from exc
