from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Literal
import hashlib
import json
from datetime import datetime, timezone
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .worker_runtime import worker_runtime_status
from .worker_memory import append_memory, read_memory, recall_memory
from .worker_registry import evaluate_registry, registry_manifest
from .analytical_agent_runtime import runtime_manifest, brain_config, validate_learning_feedback, validate_update_proposal
from .learning_engine import learning_overview, agent_learning_summary, run_feedback_improvement_cycle
from .analytical_agent_tasks import submit_research_task, get_research_task, list_research_tasks, enqueue_research_task, execute_queued_research_task, recover_interrupted_research_tasks, list_recent_task_activity, agent_supervisor_status, dispatch_queued_research_tasks, list_task_audit_events
from .research_orchestrator import orchestrate_research
from .intelligence_core import intelligence_core_status, synthesize_research, IntelligenceCoreError
from .synthesis_review import build_synthesis_review
from .skill_catalog import list_skills, load_skill
from .landing_page_builder import build_landing_page
from .markets import market_catalog
from .instruments import search_instruments
from .instrument_master import search_instrument_master, sync_reference_catalogue, register_provider_identifier
from .pipeline import system_capabilities
from .news import ingest_news
from . import indicators
from .volume_indicators import calculate_volume_indicators
from .liquidity_indicators import calculate_volume_profile
from .performance import performance_metrics
from . import workspace
from .market_data import SyntheticFixtureAdapter, MarketDataBatch
from .market_data_validation import validate_market_data_payload
from . import market_store
from .market_events import store_market_events, query_market_events
from .market_event_quality import diagnose_market_events
from .agent_network import publish_message, read_messages, network_topology
from .agent_collaboration import build_collaboration_brief
from .agent_council_api import router as agent_council_router
from .trade_flow import build_trade_flow_buckets
from .cross_market_correlation import build_cross_market_correlation
from . import watchlist
from .model_registry import list_model_integrations
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
app.include_router(agent_council_router)

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

class ResearchOrchestrationRequest(BaseModel):
 nodes: list[dict[str, Any]] = Field(min_length=1, max_length=250)
 edges: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
 inputs: dict[str, Any] = Field(default_factory=dict)
 max_workers: int = Field(default=1, ge=1, le=16)
 max_retries: int = Field(default=0, ge=0, le=3)

class ResearchSynthesisRequest(BaseModel):
 research: dict[str, Any]


class SynthesisReviewRequest(BaseModel):
 draft: str = Field(min_length=1, max_length=8000)
 claims: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
 decision: Literal["approve", "reject"]
 reviewer: str = Field(min_length=1, max_length=120)
 review_note: str = Field(default="", max_length=1000)


class AgentSupervisorDispatchRequest(BaseModel):
 limit: int = Field(default=50, ge=1, le=550)
 max_concurrency: int = Field(default=4, ge=1, le=16)


class AgentResearchTaskRequest(BaseModel):
 brief: str = Field(min_length=1, max_length=4000)
 data: dict[str, Any] | list[Any] | None = None

class AgentLearningFeedbackRequest(BaseModel):
 summary: str = Field(min_length=1, max_length=4000)
 outcome: Literal["helpful", "partially_helpful", "not_helpful", "unverified"]
 metrics: dict[str, Any] = Field(default_factory=dict)

class AgentProposalReviewRequest(BaseModel):
 reviewer: str = Field(min_length=1, max_length=120)
 decision: Literal["approve", "reject"]
 review_note: str = Field(min_length=1, max_length=2000)
 tests_checked: bool
 rollback_plan: str = Field(min_length=1, max_length=2000)

class AgentLandingPageRequest(BaseModel):
 title: str = Field(min_length=1, max_length=120)
 subtitle: str = Field(default="", max_length=300)
 description: str = Field(default="", max_length=1200)
 brand: str = Field(default="MARKET-MIND", max_length=80)
 theme: Literal["amber", "blue", "violet", "emerald"] = "amber"
 sections: list[dict[str, str]] = Field(default_factory=list, max_length=12)
 cta_label: str = Field(default="", max_length=80)
 cta_url: str = Field(default="", max_length=500)

class AgentUpdateProposalRequest(BaseModel):
 title: str = Field(min_length=1, max_length=160)
 rationale: str = Field(min_length=1, max_length=4000)
 proposed_change: str = Field(min_length=1, max_length=4000)
 evidence_refs: list[str] = Field(default_factory=list, max_length=30)

class IndicatorRequest(BaseModel):
 values: list[float] = Field(min_length=2)
 period: int = Field(default=14, ge=1, le=10000)

class VolumeIndicatorRequest(BaseModel):
 high: list[float] = Field(min_length=2, max_length=10000)
 low: list[float] = Field(min_length=2, max_length=10000)
 close: list[float] = Field(min_length=2, max_length=10000)
 volume: list[float] = Field(min_length=2, max_length=10000)
 period: int = Field(default=20, ge=1, le=10000)


class LiquidityProfileRequest(BaseModel):
 high: list[float] = Field(min_length=2, max_length=10000)
 low: list[float] = Field(min_length=2, max_length=10000)
 close: list[float] = Field(min_length=2, max_length=10000)
 volume: list[float] = Field(min_length=2, max_length=10000)
 bins: int = Field(default=48, ge=2, le=500)
 value_area_pct: float = Field(default=70.0, ge=1, le=100)


class WatchlistRequest(BaseModel):
 symbol: str = Field(min_length=1, max_length=32)


class ProviderIdentifierRequest(BaseModel):
 instrument_id: str = Field(min_length=1, max_length=128)
 provider: str = Field(min_length=1, max_length=128)
 venue: str = Field(min_length=1, max_length=128)
 external_id: str = Field(min_length=1, max_length=128)
 identifier_type: str = Field(default="provider_symbol", min_length=1, max_length=128)


class HistoricalCSVImportRequest(BaseModel):
 csv_text: str = Field(min_length=1, max_length=2_000_000)
 symbol: str = Field(min_length=1, max_length=32)
 interval: str = Field(min_length=1, max_length=16)
 source: str = Field(min_length=1, max_length=80)


class HistoricalMarketEventsRequest(BaseModel):
 events: list[dict[str, Any]] = Field(min_length=1, max_length=1000)

class WorkerMemoryRequest(BaseModel):
 memory_type: Literal["observation", "method_note", "validation_result", "open_question"]
 content: dict[str, Any] = Field(default_factory=dict)
 source_refs: list[str] = Field(default_factory=list, max_length=20)
 quality_status: Literal["verified_by_importer", "partial", "unverified", "synthetic"] = "unverified"


class AgentResearchMessageRequest(BaseModel):
 agent_id: str = Field(min_length=1, max_length=96)
 market_group: Literal["india", "us", "crypto", "forex"]
 topic: Literal["macro", "correlation", "volatility", "liquidity", "breadth", "event", "data_quality", "research_note", "regime"]
 instrument_id: str | None = Field(default=None, max_length=96)
 source_refs: list[str] = Field(default_factory=list, max_length=20)
 quality_status: Literal["verified_by_importer", "partial", "unverified", "synthetic"] = "unverified"
 payload: dict[str, Any] = Field(default_factory=dict)



class SetupReportRequest(BaseModel):
 symbol: str = Field(min_length=1, max_length=32)
 direction: Literal["long", "short"]
 entry: float = Field(gt=0)
 stop: float = Field(gt=0)
 target: float = Field(gt=0)

@app.get("/api/models")
def model_integrations():
 """List vendored model metadata without loading weights or enabling inference."""
 return list_model_integrations()


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


class MarketDataValidationRequest(BaseModel):
 payload: Any


@app.post("/api/market-data/validate")
def validate_market_data(request: MarketDataValidationRequest):
 """Return a structural validation report for a supplied market-data payload."""
 return validate_market_data_payload(request.payload)


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

@app.post("/api/workers/{worker_id}/memory")
def add_worker_memory(worker_id: str, request: WorkerMemoryRequest):
 """Append an evidence-linked research note to one registered worker profile."""
 try:
  return append_memory(
   worker_id, request.memory_type, request.content,
   request.source_refs, request.quality_status,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/memory")
def get_worker_memory(worker_id: str, memory_type: str | None = None, limit: int = 50):
 """Read append-only research notes scoped to one registered worker profile."""
 try:
  return read_memory(worker_id, memory_type, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.get("/api/workers/{worker_id}/memory/recall")
def recall_worker_memory(worker_id: str, query: str, limit: int = 5):
 """Retrieve bounded keyword-relevant worker notes for a research query."""
 try:
  return recall_memory(worker_id, query, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analytical-agents/{worker_id}/tasks")
def analytical_agent_submit_task(worker_id: str, request: AgentResearchTaskRequest):
 """Run a bounded research brief with one worker context and the shared core."""
 try:
  return submit_research_task(worker_id, request.brief, request.data)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/analytical-agents/{worker_id}/tasks/queue", status_code=202)
def analytical_agent_queue_task(worker_id: str, request: AgentResearchTaskRequest, background_tasks: BackgroundTasks):
 """Queue a persisted research task for background execution."""
 try:
  queued = enqueue_research_task(worker_id, request.brief, request.data)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 background_tasks.add_task(execute_queued_research_task, queued["task_id"])
 return queued

@app.get("/api/analytical-agents/{worker_id}/tasks")
def analytical_agent_list_tasks(worker_id: str, limit: int = 20):
 """List persisted tasks for one specialist worker."""
 try:
  return list_research_tasks(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/agent-network/activity")
def agent_network_activity(limit: int = 500):
 """Bounded persisted task activity snapshot for agent network visualization."""
 try:
  return list_recent_task_activity(limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/analytical-agent-supervisor/status")
def analytical_agent_supervisor_status():
 """Return task counts and bounded supervisor capability status."""
 return agent_supervisor_status()


@app.post("/api/analytical-agent-supervisor/dispatch")
def analytical_agent_supervisor_dispatch(request: AgentSupervisorDispatchRequest):
 """Explicitly dispatch a bounded queued-task snapshot on this process."""
 try:
  return dispatch_queued_research_tasks(request.limit, request.max_concurrency)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analytical-agent-tasks/recover")
def analytical_agent_recover_tasks():
 """Requeue tasks interrupted while running; does not dispatch them."""
 return recover_interrupted_research_tasks()

@app.get("/api/analytical-agent-tasks/{task_id}")
def analytical_agent_task_detail(task_id: str):
 """Retrieve one persisted analytical-agent task and its result."""
 record = get_research_task(task_id)
 if record is None:
  raise HTTPException(status_code=404, detail="Analytical-agent task not found")
 return record

@app.get("/api/analytical-agent-tasks/{task_id}/audit")
def analytical_agent_task_audit(
 task_id: str, limit: int = 100, event_type: str | None = None,
 before_event_id: int | None = None,
):
 """Return bounded audit history with optional event-type filter and cursor."""
 if get_research_task(task_id) is None:
  raise HTTPException(status_code=404, detail="Analytical-agent task not found")
 try:
  return list_task_audit_events(task_id, limit, event_type, before_event_id)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/analytical-agents/learning-overview")
def analytical_agent_learning_overview(limit_per_agent: int = 200):
 """Summarize feedback and proposed improvements across registered agents."""
 try:
  return learning_overview(limit_per_agent)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/analytical-agents/{worker_id}/learning-summary")
def analytical_agent_learning_summary(worker_id: str, limit: int = 200):
 """Return a bounded evidence-based feedback summary for one agent."""
 try:
  return agent_learning_summary(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analytical-agents/{worker_id}/learning-cycle")
def analytical_agent_learning_cycle(worker_id: str, limit: int = 50, min_feedback: int = 5):
 """Run a feedback-driven research-quality improvement cycle; creates review-only proposals."""
 try:
  return run_feedback_improvement_cycle(worker_id, limit=limit, min_feedback=min_feedback)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytical-agents/{worker_id}/update-proposals")
def analytical_agent_update_proposals(worker_id: str, limit: int = 100):
 """List saved improvement proposals with stable IDs and content hashes."""
 try:
  if limit < 1 or limit > 200:
   raise ValueError("limit must be between 1 and 200")
  notes = read_memory(worker_id, "method_note", limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 proposals = []
 for item in notes["memory"]:
  proposal = item.get("content", {}).get("update_proposal")
  if not isinstance(proposal, dict):
   continue
  encoded = json.dumps(proposal, sort_keys=True, ensure_ascii=False)
  proposals.append({
   "proposal_id": item["memory_id"],
   "version": 1,
   "created_at": item["created_at"],
   "content_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
   "proposal": proposal,
   "status": proposal.get("status", "pending_review"),
   "auto_apply": False,
  })
 return {"worker_id": worker_id, "count": len(proposals), "proposals": proposals,
         "note": "Version 1 is immutable evidence; approval does not automatically apply changes."}

@app.get("/api/analytical-agents/runtime")
def analytical_agent_runtime():
 """Describe 550 specialist agent contexts and the implemented learning boundary."""
 return runtime_manifest()

@app.get("/api/analytical-agents/{worker_id}/brain")
def analytical_agent_brain(worker_id: str):
 """Return one worker's distinct brain context and governed capability metadata."""
 try:
  return brain_config(worker_id)
 except ValueError as exc:
  raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/api/analytical-agents/{worker_id}/learning-feedback")
def analytical_agent_learning_feedback(worker_id: str, request: AgentLearningFeedbackRequest):
 """Persist evaluated feedback as a worker memory note; this does not train model weights."""
 try:
  feedback = validate_learning_feedback(worker_id, request.model_dump())
  record = append_memory(
   worker_id, "validation_result", feedback,
   source_refs=[], quality_status="unverified",
  )
  return {"feedback": feedback, "memory_id": record["memory_id"],
          "status": "recorded_for_future_evaluation", "model_training": False}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/analytical-agents/{worker_id}/update-proposals")
def analytical_agent_update_proposal(worker_id: str, request: AgentUpdateProposalRequest):
 """Store a proposed agent configuration improvement; never auto-apply it."""
 try:
  proposal = validate_update_proposal(worker_id, request.model_dump())
  record = append_memory(
   worker_id, "method_note", {"update_proposal": proposal},
   source_refs=proposal["evidence_refs"], quality_status="unverified",
  )
  return {"proposal": proposal, "memory_id": record["memory_id"],
          "status": "pending_review", "applied": False}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.post("/api/analytical-agents/{worker_id}/update-proposals/{proposal_id}/review")
def analytical_agent_review_update_proposal(
 worker_id: str, proposal_id: str, request: AgentProposalReviewRequest
):
 """Append a human review decision; this records evidence and never applies changes."""
 try:
  notes = read_memory(worker_id, "method_note", 200)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 proposal_record = next(
  (item for item in notes["memory"]
   if item["memory_id"] == proposal_id
   and isinstance(item.get("content", {}).get("update_proposal"), dict)),
  None,
 )
 if proposal_record is None:
  raise HTTPException(status_code=404, detail="proposal not found for this worker")
 review = {
  "review_type": "update_proposal_human_review",
  "proposal_id": proposal_id,
  "proposal_created_at": proposal_record["created_at"],
  "proposal_content_sha256": hashlib.sha256(
   json.dumps(
    proposal_record["content"]["update_proposal"],
    sort_keys=True, ensure_ascii=False
   ).encode("utf-8")
  ).hexdigest(),
  "reviewer": request.reviewer.strip(),
  "decision": request.decision,
  "review_note": request.review_note.strip(),
  "tests_checked": request.tests_checked,
  "rollback_plan": request.rollback_plan.strip(),
  "applied": False,
  "auto_apply": False,
 }
 if not review["reviewer"] or not review["review_note"] or not review["rollback_plan"]:
  raise HTTPException(status_code=422, detail="reviewer, note, and rollback plan must be non-empty")
 try:
  record = append_memory(
   worker_id, "validation_result", {"proposal_review": review},
   source_refs=[proposal_id], quality_status="unverified",
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 return {
  "review": review,
  "review_memory_id": record["memory_id"],
  "status": "review_recorded",
  "proposal_changed": False,
  "applied": False,
  "auto_apply": False,
 }

@app.get("/api/worker-registry")
def worker_registry():
 """Return the versioned 550-profile registry manifest and integrity evaluation."""
 return {"manifest": registry_manifest(), "evaluation": evaluate_registry()}


@app.get("/api/intelligence-core")
def intelligence_core():
 """Report shared-core provider configuration without probing or loading a model."""
 try:
  return intelligence_core_status()
 except IntelligenceCoreError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.post("/api/intelligence-core/synthesize")
def intelligence_core_synthesis(request: ResearchSynthesisRequest):
 """Run optional bounded synthesis on caller-supplied research JSON only."""
 try:
  return synthesize_research(request.research)
 except IntelligenceCoreError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/worker-runtime")
def worker_runtime():
 """Report specialist routing coverage and the actual inference/execution boundary."""
 return worker_runtime_status()


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

@app.post("/api/agents/{worker_id}/landing-page")
def create_agent_landing_page(worker_id: str, request: AgentLandingPageRequest):
 """Render a worker's validated landing-page draft as static HTML; never deploy or execute scripts."""
 try:
  return build_landing_page(worker_id, request.model_dump())
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/markets")
def markets():
 return market_catalog()

@app.get("/api/system/capabilities")
def capabilities():
 return system_capabilities()

@app.get("/api/instruments")
def instruments(q: str = "", market: str | None = None, market_group: str | None = None, limit: int = 30):
 """Search reference instruments by asset class and requested market domain."""
 if market_group is not None and market_group not in {"india", "us", "crypto", "forex"}:
  raise HTTPException(status_code=400, detail="market_group must be one of india,us,crypto,forex")
 if limit < 1 or limit > 100:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
 return search_instruments(q, market, limit, market_group)

@app.get("/api/instrument-master")
def instrument_master(q: str = "", market_group: str | None = None,
                      market: str | None = None, limit: int = 50):
 """Search persistent multi-market reference metadata; no quote data is implied."""
 try:
  sync_reference_catalogue()
  return search_instrument_master(q, market_group, market, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/instrument-master/identifiers")
def add_provider_identifier(request: ProviderIdentifierRequest):
 """Register a provider-native identifier against a canonical instrument ID."""
 try:
  sync_reference_catalogue()
  return register_provider_identifier(
   request.instrument_id, request.provider, request.venue,
   request.external_id, request.identifier_type,
  )
 except KeyError as exc:
  raise HTTPException(status_code=404, detail=str(exc)) from exc
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/news")
async def news_feed():
 return await ingest_news()

@app.post("/api/news/ingest")
async def news():
 result=await ingest_news()
 return result

@app.post("/api/indicators/volume")
def calculate_volume(request: VolumeIndicatorRequest):
 """Calculate descriptive OHLCV volume indicators for historical research only."""
 try:
  return calculate_volume_indicators(request.high, request.low, request.close, request.volume, request.period)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/indicators/liquidity-profile")
def calculate_liquidity_profile(request: LiquidityProfileRequest):
 """Calculate approximate OHLCV volume-at-price profile for historical research."""
 try:
  return calculate_volume_profile(
   request.high, request.low, request.close, request.volume,
   request.bins, request.value_area_pct,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.get("/api/agent-network")
def agent_network():
 """Describe the deterministic four-market research message mesh."""
 return network_topology()


@app.post("/api/agent-network/messages")
def publish_agent_research_message(request: AgentResearchMessageRequest):
 """Publish a structured research note to the shared four-market message bus."""
 try:
  return publish_message(request.model_dump())
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/agent-network/messages")
def agent_research_messages(
 market_group: str | None = None,
 topic: str | None = None,
 limit: int = 100,
):
 """Read shared research notes, optionally filtered by market or topic."""
 try:
  return read_messages(market_group, topic, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/agent-network/brief")
def agent_collaboration_brief(topic: str | None = None, limit: int = 500):
 """Build a deterministic cross-market roundtable from shared research notes."""
 try:
  shared = read_messages(None, topic, limit)
  return build_collaboration_brief(shared["messages"])
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/market-data/events")
def import_historical_market_events(request: HistoricalMarketEventsRequest):
 """Import validated historical trades, quotes, depth and reference observations."""
 try:
  return store_market_events(request.events)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market-data/events")
def historical_market_events(
 instrument_id: str | None = None,
 event_type: str | None = None,
 provider: str | None = None,
 venue: str | None = None,
 start: str | None = None,
 end: str | None = None,
 limit: int = 500,
):
 """Query stored historical microstructure events with provenance metadata."""
 try:
  return query_market_events(instrument_id, event_type, provider, venue, start, end, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market-data/trade-flow")
def historical_trade_flow(
 instrument_id: str,
 bucket_seconds: int = 60,
 provider: str | None = None,
 venue: str | None = None,
 start: str | None = None,
 end: str | None = None,
 limit: int = 5000,
):
 """Aggregate imported historical trades; CVD requires complete side classification."""
 try:
  result = query_market_events(
   instrument_id=instrument_id, event_type="trade", provider=provider,
   venue=venue, start=start, end=end, limit=limit,
  )
  return build_trade_flow_buckets(
   result["events"], bucket_seconds, result["total_matching"], limit,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/cross-market-correlation")
def cross_market_correlation(
 symbols: str,
 interval: str = "1d",
 limit: int = 500,
 min_observations: int = 20,
):
 """Compare aligned historical close-to-close returns across stored instruments."""
 names = sorted({item.strip().upper() for item in symbols.split(",") if item.strip()})
 if len(names) < 2 or len(names) > 12:
  raise HTTPException(status_code=400, detail="symbols must contain 2 to 12 unique instruments")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 3 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 3 and 5000")
 histories = {name: market_store.get_bars(name, interval, limit) for name in names}
 try:
  return build_cross_market_correlation(histories, interval, min_observations)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market-data/events/quality")
def historical_market_event_quality(
 instrument_id: str | None = None,
 event_type: str | None = None,
 provider: str | None = None,
 venue: str | None = None,
 start: str | None = None,
 end: str | None = None,
 limit: int = 5000,
):
 """Diagnose sequence, timestamp and snapshot consistency in stored historical events."""
 try:
  result = query_market_events(instrument_id, event_type, provider, venue, start, end, limit)
  diagnostics = diagnose_market_events(result["events"])
  return {**diagnostics, "matching_events": result["total_matching"],
          "sampled_events": result["count"], "limit": limit,
          "data_note": "Diagnostics cover the returned sample only; they do not establish provider authenticity, sequence semantics or complete history."}
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
 if not isinstance(checkpoint, dict):
  raise HTTPException(status_code=409, detail="Checkpoint has an invalid format.")
 expected = _workflow_request_fingerprint(request_payload)
 if checkpoint.get("request_fingerprint") != expected:
  raise HTTPException(status_code=409, detail="Checkpoint does not match the original workflow request.")
 if checkpoint.get("checkpoint_schema_version") != 1:
  raise HTTPException(status_code=409, detail="Checkpoint schema version is missing or unsupported.")
 checkpoint_timestamp = checkpoint.get("checkpointed_at")
 if not isinstance(checkpoint_timestamp, str):
  raise HTTPException(status_code=409, detail="Checkpoint timestamp is missing or invalid.")
 try:
  datetime.fromisoformat(checkpoint_timestamp.replace("Z", "+00:00"))
 except ValueError as exc:
  raise HTTPException(status_code=409, detail="Checkpoint timestamp is invalid.") from exc
 completed_list = checkpoint.get("completed_node_ids", [])
 results = checkpoint.get("results", {})
 tasks = checkpoint.get("tasks", {})
 if (not isinstance(completed_list, list)
     or any(not isinstance(node_id, str) or not node_id for node_id in completed_list)
     or len(completed_list) != len(set(completed_list))
     or not isinstance(results, dict)
     or not isinstance(tasks, dict)):
  raise HTTPException(status_code=409, detail="Checkpoint has an invalid internal structure.")
 completed_ids = set(completed_list)
 if (not completed_ids.issubset(known_ids)
     or not set(results).issubset(known_ids)
     or not set(tasks).issubset(known_ids)):
  raise HTTPException(status_code=409, detail="Checkpoint contains nodes not present in the saved workflow.")
 allowed_statuses = {"queued", "running", "completed", "failed", "skipped"}
 if any(not isinstance(record, dict)
        or record.get("node_id", node_id) != node_id
        or record.get("status") not in allowed_statuses
        for node_id, record in tasks.items()):
  raise HTTPException(status_code=409, detail="Checkpoint contains an invalid task record.")
 if any(node_id not in results or tasks.get(node_id, {}).get("status") != "completed"
        for node_id in completed_ids):
  raise HTTPException(status_code=409, detail="Checkpoint is incomplete or internally inconsistent.")
 if not set(results).issubset(completed_ids):
  raise HTTPException(status_code=409, detail="Checkpoint contains results for nodes not marked completed.")
 completed_layers = checkpoint.get("completed_layers", 0)
 if (not isinstance(completed_layers, int) or isinstance(completed_layers, bool)
     or completed_layers < 0):
  raise HTTPException(status_code=409, detail="Checkpoint has an invalid completed-layer count.")


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



@app.post("/api/research/synthesis/review")
def review_research_synthesis(request: SynthesisReviewRequest):
 """Record a human review decision for an untrusted synthesis draft.

 This prototype endpoint is stateless and must remain behind trusted local access;
 authentication/authorization is required before public deployment.
 """
 try:
  review = build_synthesis_review(
   draft=request.draft, claims=request.claims,
   source_registry=request.source_registry, decision=request.decision,
   reviewer=request.reviewer, review_note=request.review_note,
  )
  return workspace.save_synthesis_review(review)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/research/orchestrate")
def orchestrate_research_request(request: ResearchOrchestrationRequest):
 """Coordinate specialist workers through the shared deterministic intelligence core."""
 try:
  return orchestrate_research(
   nodes=request.nodes, edges=request.edges, inputs=request.inputs,
   max_workers=request.max_workers, max_retries=request.max_retries,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


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
 if record.get("request_error"):
  raise HTTPException(status_code=409, detail=record["request_error"])
 if record.get("checkpoint_error"):
  raise HTTPException(status_code=409, detail=record["checkpoint_error"])
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
