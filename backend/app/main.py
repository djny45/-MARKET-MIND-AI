from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Literal
import hashlib
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers
from .worker_runtime import worker_runtime_status
from .worker_memory import append_memory, read_memory, recall_memory, review_learning_candidate, list_learning_candidates, recall_approved_learning_candidates, review_improvement_proposal, list_improvement_proposals
from .staging_experiments import create_staging_experiment, run_staging_benchmark, list_staging_experiments, summarize_staging_experiments, summarize_repeatability, summarize_staging_provenance, summarize_research_quality_dashboard
from .learning_feedback import evaluate_learning_feedback
from .worker_registry import evaluate_registry, registry_manifest
from .analytical_agent_runtime import runtime_manifest, brain_config, validate_learning_feedback, validate_update_proposal
from .learning_engine import learning_overview, agent_learning_summary, run_feedback_improvement_cycle, build_feedback_staging_plan
from .specialist_router import route_research_brief
from .analytical_agent_tasks import retry_failed_research_task, cancel_queued_research_task, submit_research_task, get_research_task, list_research_tasks, enqueue_research_task, execute_queued_research_task, recover_interrupted_research_tasks, list_recent_task_activity, agent_supervisor_status, dispatch_queued_research_tasks, list_task_audit_events, get_task_quality_evaluation
from .research_orchestrator import orchestrate_research
from .intelligence_core import intelligence_core_status, synthesize_research, IntelligenceCoreError
from .synthesis_review import build_synthesis_review, build_synthesis_review_packet, validate_claim_review_checklist
from .research_quality_eval import evaluate_research_draft
from .research_evidence_audit import audit_evidence
from .research_citation_audit import audit_claim_citations
from .research_benchmark import run_offline_research_benchmark
from .skill_catalog import list_skills, load_skill, build_skill_protocol
from .open_source_intake import build_source_candidate
from .open_source_license_review import build_license_review_checklist
from .github_research_discovery import discover_github_repositories
from .github_pinned_extraction import fetch_pinned_text_candidate
from .github_license_evidence import fetch_pinned_license_evidence
from .github_research_chunking import chunk_research_text
from .github_research_quality import score_source_evidence
from .github_research_review_bundle import build_review_bundle
from .landing_page_builder import build_landing_page
from .markets import market_catalog
from .instruments import search_instruments
from .instrument_master import search_instrument_master, sync_reference_catalogue, register_provider_identifier
from .pipeline import system_capabilities
from .news import ingest_news
from . import social_sources
from urllib.parse import urlparse
from . import indicators
from .volume_indicators import calculate_volume_indicators
from .liquidity_indicators import calculate_volume_profile
from .performance import performance_metrics
from . import workspace
from .market_data import SyntheticFixtureAdapter, MarketDataBatch
from .yahoo_finance_adapter import YahooFinanceAdapter
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
from .autonomous_research import run_autonomous_research
from .market_discovery import MarketCandidate
from .multi_timeframe import build_multi_timeframe_report, SUPPORTED_INTERVALS
from .deep_analysis import build_deep_analysis_report
from .research_timeline import build_research_timeline
from .csv_import import parse_historical_csv
from .historical_quality import build_historical_quality_diagnostics
from .source_comparison import compare_source_observations
from .research_export import build_research_evidence_bundle
from .research_export_compare import compare_research_exports
import json
import os
import uuid
from fastapi.responses import Response

@asynccontextmanager
async def lifespan(app: FastAPI):
 """Run guarded task recovery once when the API process starts."""
 recover_stale_tasks_on_startup()
 yield


app = FastAPI(
 title="MARKET-MIND-AI API",
 version="0.2.0",
 description="Multi-market, evidence-first research pipeline. No brokerage execution.",
 lifespan=lifespan,
)
# Keep browser origins explicit using a comma-separated allowlist.
_frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agent_council_router)


def recover_stale_tasks_on_startup():
 """Best-effort SQLite task recovery at process startup (single-process mode)."""
 if os.getenv("MARKET_MIND_STARTUP_RECOVERY", "true").strip().lower() in {"0", "false", "no", "off"}:
  app.state.task_startup_recovery = {"status": "disabled", "requeued_interrupted_count": 0}
  return app.state.task_startup_recovery
 try:
  recovery = recover_interrupted_research_tasks()
  app.state.task_startup_recovery = {"status": "completed", **recovery}
 except Exception as exc:
  # Recovery must not prevent the research API from starting. Keep only the
  # exception class in the status snapshot; do not expose internal details.
  app.state.task_startup_recovery = {
   "status": "failed", "error_type": type(exc).__name__,
   "requeued_interrupted_count": 0,
  }
 return app.state.task_startup_recovery



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
 evidence_claims: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)

class ResearchSynthesisRequest(BaseModel):
 research: dict[str, Any]


class ResearchQualityEvaluationRequest(BaseModel):
 draft: str = Field(min_length=1, max_length=20000)
 claims: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
 baseline: dict[str, Any] | None = None

class ResearchCitationAuditRequest(BaseModel):
 claims: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class ResearchEvidenceAuditRequest(BaseModel):
 claims: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)





class ResearchBenchmarkRequest(BaseModel):
 cases: list[dict[str, Any]] = Field(min_length=1, max_length=100)
 baseline: dict[str, Any] | None = None
 regression_threshold: float = Field(default=0.05, ge=0, le=1)

class SynthesisReviewRequest(BaseModel):
 draft: str = Field(min_length=1, max_length=8000)
 claims: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
 source_registry: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
 decision: Literal["approve", "reject"]
 reviewer: str = Field(min_length=1, max_length=120)
 review_note: str = Field(default="", max_length=1000)
 claim_review_checklist: list[dict[str, Any]] | None = Field(default=None, max_length=100)


class AgentSupervisorDispatchRequest(BaseModel):
 limit: int = Field(default=50, ge=1, le=550)
 max_concurrency: int = Field(default=4, ge=1, le=16)


class AgentResearchTaskRequest(BaseModel):
 brief: str = Field(min_length=1, max_length=4000)
 data: dict[str, Any] | list[Any] | None = None


class SpecialistResearchQueueRequest(AgentResearchTaskRequest):
 max_specialists: int = Field(default=3, ge=1, le=10)

class AgentLearningFeedbackRequest(BaseModel):
 summary: str = Field(min_length=1, max_length=4000)
 outcome: Literal["helpful", "partially_helpful", "not_helpful", "unverified"]
 metrics: dict[str, Any] = Field(default_factory=dict)

class GitHubRepositoryDiscoveryRequest(BaseModel):
 query: str = Field(min_length=1, max_length=180)
 limit: int = Field(default=5, ge=1, le=10)

class GitHubPinnedExtractionRequest(BaseModel):
 repository_url: str = Field(min_length=1, max_length=300)
 commit_sha: str = Field(min_length=1, max_length=40)
 file_path: str = Field(min_length=1, max_length=500)
 license_spdx: str = Field(min_length=1, max_length=50)
 source_kind: Literal["documentation", "source_excerpt", "research_note"] = "documentation"

class GitHubPinnedLicenseEvidenceRequest(BaseModel):
 repository_url: str = Field(min_length=1, max_length=300)
 commit_sha: str = Field(min_length=1, max_length=40)

class GitHubResearchChunkingRequest(BaseModel):
 memory_id: str = Field(min_length=1, max_length=64)
 max_chars: int = Field(default=4000, ge=200, le=8000)
 overlap_chars: int = Field(default=200, ge=0, le=3999)

class GitHubResearchQualityRequest(BaseModel):
 candidate_memory_id: str = Field(min_length=1, max_length=64)

class OpenSourceLicenseReviewDispositionRequest(BaseModel):
 candidate_memory_id: str = Field(min_length=1, max_length=64)
 checklist_memory_id: str = Field(min_length=1, max_length=64)
 reviewer: str = Field(min_length=1, max_length=120)
 disposition: Literal["reviewed", "needs_more_evidence", "refer_to_legal", "do_not_use"]
 review_note: str = Field(default="", max_length=2000)

class GitHubResearchReviewBundleRequest(BaseModel):
 candidate_memory_id: str = Field(min_length=1, max_length=64)

class OpenSourceIntakeRequest(BaseModel):
 repository_url: str = Field(min_length=1, max_length=300)
 commit_sha: str = Field(min_length=1, max_length=40)
 file_path: str = Field(min_length=1, max_length=500)
 license_spdx: str = Field(min_length=1, max_length=50)
 content: str = Field(min_length=1, max_length=8000)
 source_kind: Literal["documentation", "source_excerpt", "research_note"] = "documentation"

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



class WorkerMemoryCandidateReviewRequest(BaseModel):
 decision: Literal["approved", "rejected", "needs_revision"]
 reviewer: str = Field(min_length=1, max_length=120)
 rationale: str = Field(default="", max_length=2000)

class WorkerLearningFeedbackRequest(BaseModel):
 current_metrics: dict[str, Any] = Field(min_length=1, max_length=100)
 stale_after_days: int = Field(default=30, ge=1, le=3650)
 tolerance: float = Field(default=0.0001, ge=0, le=1e12)

class ImprovementProposalReviewRequest(BaseModel):
 decision: Literal["approved_for_staging", "rejected", "needs_revision"]
 reviewer: str = Field(min_length=1, max_length=120)
 rationale: str = Field(default="", max_length=2000)

class StagingExperimentRequest(BaseModel):
 benchmark_id: str = Field(min_length=1, max_length=120)
 baseline_metrics: dict[str, float] = Field(min_length=1, max_length=10)
 candidate_metrics: dict[str, float] = Field(min_length=1, max_length=10)
 reviewer: str = Field(min_length=1, max_length=120)
 notes: str = Field(default="", max_length=2000)

class StagingBenchmarkRequest(BaseModel):
 baseline_cases: list[dict[str, Any]] = Field(min_length=1, max_length=100)
 candidate_cases: list[dict[str, Any]] = Field(min_length=1, max_length=100)
 reviewer: str = Field(min_length=1, max_length=120)
 notes: str = Field(default="", max_length=2000)

class StagingConfigPatchRequest(BaseModel):
 baseline_cases: list[dict[str, Any]] = Field(min_length=1, max_length=100)
 candidate_cases: list[dict[str, Any]] = Field(min_length=1, max_length=100)
 config_patch: dict[str, Any]
 reviewer: str = Field(min_length=1, max_length=120)
 notes: str = Field(default="", max_length=2000)

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


class SocialFeedRequest(BaseModel):
 source: str = Field(min_length=1, max_length=80)
 feed_url: str = Field(min_length=1, max_length=500)


class EvidenceMergeRequest(BaseModel):
 news_items: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
 social_items: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class EvidenceReportRequest(EvidenceMergeRequest):
 topic: str = Field(default="general research", min_length=1, max_length=300)


class SocialResearchRequest(BaseModel):
 feeds: list[SocialFeedRequest] = Field(min_length=1, max_length=20)
 concurrency: int = Field(default=3, ge=1, le=8)


class AutonomousResearchCandidateRequest(BaseModel):
 symbol: str = Field(min_length=1, max_length=32)
 venue: str = Field(min_length=1, max_length=80)
 asset_class: str = Field(min_length=1, max_length=40)
 source: str = Field(min_length=1, max_length=80)
 observed_at: datetime
 data_available: bool = True
 data_quality: float = Field(ge=0, le=1)
 activity: float | None = Field(default=None, ge=0, le=1)
 volatility: float | None = Field(default=None, ge=0, le=1)
 news_attention: float | None = Field(default=None, ge=0, le=1)
 social_attention: float | None = Field(default=None, ge=0, le=1)
 timeframes: list[str] = Field(default_factory=lambda: ["1d"], max_length=4)
 notes: list[str] = Field(default_factory=list, max_length=20)


class AutonomousResearchFixtureRequest(BaseModel):
 candidates: list[AutonomousResearchCandidateRequest] = Field(min_length=1, max_length=20)
 research_limit: int = Field(default=10, ge=1, le=20)
 bars_limit: int = Field(default=5, ge=2, le=5)
 use_shared_ai: bool = False


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




@app.post("/api/research/specialist-routing")
def research_specialist_routing(request: AgentResearchTaskRequest):
 """Recommend specialist worker profiles using deterministic keyword matching."""
 try:
  return route_research_brief(request.brief, request.data, limit=10)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/research/route-and-queue", status_code=202)
def route_and_queue_research(request: SpecialistResearchQueueRequest, background_tasks: BackgroundTasks):
 """Route a brief to matched specialists, persist one task per selected profile, and schedule process-local execution."""
 try:
  routing = route_research_brief(request.brief, request.data, limit=request.max_specialists)
  queued_tasks = []
  for candidate in routing["candidates"]:
   worker_id = candidate["worker_id"]
   queued = enqueue_research_task(worker_id, request.brief, request.data)
   background_tasks.add_task(execute_queued_research_task, queued["task_id"])
   queued_tasks.append({**queued, "department": candidate["department"], "specialty": candidate["specialty"],
                        "routing_score": candidate["routing_score"]})
  return {
   "routing": routing,
   "queued_count": len(queued_tasks),
   "tasks": queued_tasks,
   "execution_mode": "process_local_background_tasks",
   "limitations": [
    "Routing is deterministic keyword matching, not semantic reasoning.",
    "Each task uses the same configured intelligence provider; worker profiles supply role context, not separate models.",
    "Background execution is local to this API process and is not a durable distributed queue.",
    "No market data is fetched; the brief and supplied data are the only research inputs.",
   ],
  }
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/memory")
def get_worker_memory(worker_id: str, memory_type: str | None = None, limit: int = 50):
 """Read append-only research notes scoped to one registered worker profile."""
 try:
  return read_memory(worker_id, memory_type, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc






@app.post("/api/workers/{worker_id}/learning-feedback/evaluate")
def evaluate_worker_learning_feedback(worker_id: str, request: WorkerLearningFeedbackRequest):
 """Compare supplied metrics with reviewed evidence; differences require human interpretation."""
 try:
  return evaluate_learning_feedback(
   worker_id, request.current_metrics,
   stale_after_days=request.stale_after_days,
   tolerance=request.tolerance,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/improvement-proposals/{proposal_memory_id}/staging-plan")
def get_feedback_staging_plan(worker_id: str, proposal_memory_id: str):
 """Build a review-gated experiment checklist; does not run or promote changes."""
 try:
  return build_feedback_staging_plan(worker_id, proposal_memory_id)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/improvement-proposals")
def get_worker_improvement_proposals(worker_id: str, limit: int = 50):
 """List generated research improvement proposals and append-only review state."""
 try:
  return list_improvement_proposals(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/improvement-proposals/{proposal_memory_id}/review")
def review_worker_improvement_proposal(
 worker_id: str, proposal_memory_id: str, request: ImprovementProposalReviewRequest,
):
 """Record a staging-only human review; never changes code or deploys."""
 try:
  return review_improvement_proposal(
   worker_id, proposal_memory_id, request.decision, request.reviewer, request.rationale,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.post("/api/workers/{worker_id}/improvement-proposals/{proposal_memory_id}/staging-experiments")
def create_worker_staging_experiment(worker_id: str, proposal_memory_id: str, request: StagingExperimentRequest):
 """Record a human-run, metrics-only staging comparison for an approved proposal."""
 try:
  return create_staging_experiment(worker_id, proposal_memory_id, request.model_dump())
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.post("/api/workers/{worker_id}/improvement-proposals/{proposal_memory_id}/staging-benchmark")
def run_worker_staging_benchmark(worker_id: str, proposal_memory_id: str, request: StagingBenchmarkRequest):
 """Run the built-in deterministic benchmark on two caller-supplied fixture sets."""
 try:
  return run_staging_benchmark(worker_id, proposal_memory_id, request.model_dump())
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/improvement-proposals/{proposal_memory_id}/staging-config-evaluation")
def run_worker_staging_config_evaluation(worker_id: str, proposal_memory_id: str, request: StagingConfigPatchRequest):
 """Evaluate a structured, whitelisted evaluator config change against paired offline fixtures."""
 try:
  payload = request.model_dump()
  payload["config_patch"] = request.config_patch
  return run_staging_benchmark(worker_id, proposal_memory_id, payload)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/staging-experiments")
def get_worker_staging_experiments(worker_id: str, limit: int = 50):
 try:
  return list_staging_experiments(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/workers/{worker_id}/staging-experiments/repeatability")
def get_worker_staging_repeatability(worker_id: str, limit: int = 200, min_trials: int = 3):
 """Summarize consistency across exact repeated fixture/config runs."""
 try:
  return summarize_repeatability(worker_id, limit, min_trials)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.get("/api/workers/{worker_id}/staging-experiments/provenance")
def get_worker_staging_provenance(worker_id: str, limit: int = 100):
 """Audit declared provenance metadata on stored offline benchmark runs."""
 try:
  return summarize_staging_provenance(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/workers/{worker_id}/research-quality-dashboard")
def get_research_quality_dashboard(worker_id: str, limit: int = 100):
 """Consolidate offline staging experiment diagnostics for human review."""
 try:
  return summarize_research_quality_dashboard(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/staging-experiments/summary")
def get_worker_staging_experiment_summary(worker_id: str, limit: int = 100):
 """Summarize recent staging experiments descriptively; does not rank strategies."""
 try:
  return summarize_staging_experiments(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/learning-candidates/approved-context")
def recall_worker_approved_learning_candidates(worker_id: str, query: str, limit: int = 5):
 """Retrieve bounded keyword-matched approved learning evidence for explicit context use."""
 try:
  return recall_approved_learning_candidates(worker_id, query, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/workers/{worker_id}/learning-candidates")
def get_worker_learning_candidates(worker_id: str, limit: int = 50):
 """List metrics-only learning candidates and append-only review history."""
 try:
  return list_learning_candidates(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/workers/{worker_id}/memory/{memory_id}/review")
def review_worker_learning_candidate(worker_id: str, memory_id: str, request: WorkerMemoryCandidateReviewRequest):
 """Append an operator review event for a metrics-only research learning candidate.

 This labels a candidate for human/operator workflow only; it does not train a model,
 alter strategy, or automatically inject approved content into agent instructions.
 """
 try:
  return review_learning_candidate(
   worker_id, memory_id, request.decision, request.reviewer, request.rationale,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/workers/{worker_id}/github-repository-discovery")
def discover_worker_github_repositories(worker_id: str, request: GitHubRepositoryDiscoveryRequest):
 """Discover bounded public GitHub repository metadata for research only.

 Results are persisted as unverified observation notes. Discovery does not fetch
 source files, verify licensing, execute code, or promote skills.
 """
 try:
  result = discover_github_repositories(request.query, request.limit)
  memory_record = append_memory(
   worker_id, "observation",
   {"record_type": "github_repository_discovery", **result},
   ["https://api.github.com/search/repositories"],
   "unverified",
  )
  return {"discovery": result, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 except RuntimeError as exc:
  raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/extract-pinned-github-file")
def extract_pinned_github_file(worker_id: str, request: GitHubPinnedExtractionRequest):
 """Fetch one small text file at a pinned public GitHub commit.

 The resulting content is stored as unverified, review-pending evidence only.
 No third-party code is executed, copied into runtime, or promoted.
 """
 try:
  candidate = fetch_pinned_text_candidate(**request.model_dump())
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "open_source_learning_candidate", **candidate},
   [f"open_source:{candidate['repository_url']}@{candidate['commit_sha']}:{candidate['file_path']}"],
   "unverified",
  )
  return {"candidate": candidate, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 except RuntimeError as exc:
  raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/score-open-source-evidence")
def score_open_source_evidence(worker_id: str, request: GitHubResearchQualityRequest):
 """Score provenance-field completeness only; never establish truth or approval."""
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
  candidate_record = next(
   (item for item in records if item.get("memory_id") == request.candidate_memory_id), None
  )
  if candidate_record is None:
   raise ValueError("open-source candidate was not found in the recent worker memory window")
  candidate = candidate_record.get("content")
  if not isinstance(candidate, dict) or candidate.get("record_type") != "open_source_learning_candidate":
   raise ValueError("memory record is not an open-source learning candidate")
  repo_url = candidate.get("repository_url")
  commit_sha = candidate.get("commit_sha")
  license_record = next(
   (item.get("content", {}) for item in records
    if isinstance(item.get("content"), dict)
    and item["content"].get("record_type") == "pinned_github_license_evidence"
    and item["content"].get("repository_url") == repo_url
    and item["content"].get("commit_sha") == commit_sha), None
  )
  score = score_source_evidence(candidate, license_record)
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "github_research_evidence_quality",
    "candidate_memory_id": request.candidate_memory_id, **score},
   [f"worker-memory:{request.candidate_memory_id}"], "unverified",
  )
  return {"quality_score": score, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/review-open-source-license")
def review_open_source_license(worker_id: str, request: GitHubResearchQualityRequest):
 """Build and persist a human-review checklist for an intake candidate.

 Checklist generation validates pinned evidence and candidate integrity, but
 never approves license compatibility or enables code reuse/execution.
 """
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
  candidate_record = next(
   (item for item in records if item.get("memory_id") == request.candidate_memory_id), None
  )
  if candidate_record is None:
   raise ValueError("open-source candidate was not found in the recent worker memory window")
  candidate = candidate_record.get("content")
  if not isinstance(candidate, dict) or candidate.get("record_type") != "open_source_learning_candidate":
   raise ValueError("memory record is not an open-source learning candidate")
  matching_evidence = [
   item.get("content", {}) for item in records
   if isinstance(item.get("content"), dict)
   and item["content"].get("record_type") == "pinned_github_license_evidence"
   and item["content"].get("repository_url") == candidate.get("repository_url")
   and str(item["content"].get("commit_sha", "")).lower() == str(candidate.get("commit_sha", "")).lower()
  ]
  if len(matching_evidence) > 1:
   raise ValueError("multiple license evidence records match this repository and commit; resolve the duplicate records before review")
  evidence = matching_evidence[0] if matching_evidence else None
  checklist = build_license_review_checklist(candidate, evidence)
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "open_source_license_review_checklist",
    "candidate_memory_id": request.candidate_memory_id, **checklist},
   [f"worker-memory:{request.candidate_memory_id}"], "unverified",
  )
  return {"checklist": checklist, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/record-open-source-license-review")
def record_open_source_license_review(worker_id: str, request: OpenSourceLicenseReviewDispositionRequest):
 """Append a human-entered review disposition; this is not a license approval."""
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
  candidate_record = next(
   (item for item in records if item.get("memory_id") == request.candidate_memory_id), None
  )
  checklist_record = next(
   (item for item in records if item.get("memory_id") == request.checklist_memory_id), None
  )
  if candidate_record is None or checklist_record is None:
   raise ValueError("candidate or checklist was not found in the recent worker memory window")
  candidate = candidate_record.get("content")
  checklist = checklist_record.get("content")
  if not isinstance(candidate, dict) or candidate.get("record_type") != "open_source_learning_candidate":
   raise ValueError("candidate memory is not an open-source intake candidate")
  if not isinstance(checklist, dict) or checklist.get("record_type") != "open_source_license_review_checklist":
   raise ValueError("checklist memory is not a license-review checklist")
  if checklist.get("candidate_memory_id") != request.candidate_memory_id:
   raise ValueError("checklist does not reference the supplied candidate")
  if checklist.get("candidate_id") != candidate.get("candidate_id"):
   raise ValueError("checklist candidate identifier does not match candidate memory")
  # Reviewer identity is self-reported in this prototype; authentication is not implemented.
  review_record = {
   "record_type": "open_source_license_review_disposition",
   "candidate_memory_id": request.candidate_memory_id,
   "checklist_memory_id": request.checklist_memory_id,
   "candidate_id": candidate.get("candidate_id"),
   "repository_url": candidate.get("repository_url"),
   "commit_sha": candidate.get("commit_sha"),
   "reviewer": request.reviewer.strip(),
   "reviewer_identity_verified": False,
   "disposition": request.disposition,
   "review_note": request.review_note,
   "review_status": "human_disposition_recorded_unverified",
   "reuse_approved": False,
   "execution_allowed": False,
   "automatic_copy_allowed": False,
   "legal_conclusion": False,
   "note": "This records a self-reported review disposition only. It is not legal advice, license approval, or authorization to reuse or execute source.",
  }
  review_record["review_record_sha256"] = hashlib.sha256(
   json.dumps(review_record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
  ).hexdigest()
  memory_record = append_memory(
   worker_id, "validation_result", review_record,
   [f"worker-memory:{request.candidate_memory_id}", f"worker-memory:{request.checklist_memory_id}"],
   "unverified",
  )
  return {"review": review_record, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/open-source-license-reviews")
def list_open_source_license_reviews(worker_id: str, limit: int = 50):
 """List recent license-review dispositions without implying approval."""
 if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 reviews = []
 for item in records:
  review = item.get("content")
  if not isinstance(review, dict) or review.get("record_type") != "open_source_license_review_disposition":
   continue
  stored_digest = review.get("review_record_sha256")
  unsigned_review = {key: value for key, value in review.items() if key != "review_record_sha256"}
  computed_digest = hashlib.sha256(
   json.dumps(unsigned_review, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
  ).hexdigest()
  reviews.append({
   "memory_id": item["memory_id"],
   "created_at": item["created_at"],
   "quality_status": item["quality_status"],
   "review": review,
   "integrity_status": "valid" if stored_digest == computed_digest else "missing_or_mismatched",
  })

 return {
  "worker_id": worker_id,
  "count": min(len(reviews), limit),
  "reviews": reviews[:limit],
  "scan_limit": 200,
  "memory_records_scanned": len(records),
  "scan_truncated": read_memory(worker_id, "validation_result", 200)["total_matching"] > len(records),
  "note": "Recent append-only records only; reviewer identity is unverified and dispositions are not license clearance or reuse permission.",
 }


@app.post("/api/workers/{worker_id}/chunk-open-source-candidate")
def chunk_open_source_candidate(worker_id: str, request: GitHubResearchChunkingRequest):
 """Chunk a previously stored text candidate for evidence-linked review.

 Chunk text is returned for inspection; only compact hashes/offsets are persisted.
 """
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
  candidate = next((item for item in records if item.get("memory_id") == request.memory_id), None)
  if candidate is None:
   raise ValueError("open-source candidate was not found in the recent worker memory window")
  content = candidate.get("content")
  if not isinstance(content, dict) or content.get("record_type") != "open_source_learning_candidate":
   raise ValueError("memory record is not an open-source learning candidate")
  source_text = content.get("content")
  if not isinstance(source_text, str):
   raise ValueError("candidate does not contain a text snapshot")
  chunked = chunk_research_text(
   source_text, max_chars=request.max_chars, overlap_chars=request.overlap_chars,
  )
  compact_chunks = [
   {"index": item["index"], "start_char": item["start_char"],
    "end_char": item["end_char"], "sha256": item["sha256"]}
   for item in chunked["chunks"]
  ]
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "github_research_chunk_manifest",
    "source_memory_id": request.memory_id,
    "source_sha256": chunked["source_sha256"],
    "source_chars": chunked["source_chars"],
    "chunk_count": chunked["chunk_count"],
    "chunks": compact_chunks,
    "review_required": True,
    "semantic_extraction": False,
    "auto_promotion": False},
   [f"worker-memory:{request.memory_id}"], "unverified",
  )
  return {"chunking": chunked, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/build-open-source-review-bundle")
def build_open_source_review_bundle(worker_id: str, request: GitHubResearchReviewBundleRequest):
 """Assemble existing source, chunk, license, and provenance records for human review."""
 try:
  records = read_memory(worker_id, "validation_result", 200)["memory"]
  candidate = next(
   (item for item in records if item.get("memory_id") == request.candidate_memory_id), None
  )
  if candidate is None:
   raise ValueError("open-source candidate was not found in the recent worker memory window")
  return {"review_bundle": build_review_bundle(candidate, records)}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/verify-pinned-github-license")
def verify_pinned_github_license(worker_id: str, request: GitHubPinnedLicenseEvidenceRequest):
 """Retrieve license-file evidence from a pinned commit for human review only.

 This endpoint does not determine license compatibility or provide legal advice.
 """
 try:
  evidence = fetch_pinned_license_evidence(**request.model_dump())
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "pinned_github_license_evidence", **evidence},
   [f"license_evidence:{evidence['repository_url']}@{evidence['commit_sha']}"],
   "unverified",
  )
  return {"evidence": evidence, "memory_record": memory_record}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 except RuntimeError as exc:
  raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/workers/{worker_id}/open-source-candidates")
def register_open_source_candidate(worker_id: str, request: OpenSourceIntakeRequest):
 """Store a pinned, license-allowlisted source snapshot as pending review.

 Source content is data only: no execution, automatic copying, or promotion.
 """
 try:
  candidate = build_source_candidate(**request.model_dump())
  memory_record = append_memory(
   worker_id, "validation_result",
   {"record_type": "open_source_learning_candidate", **candidate},
   [f"open_source:{candidate['repository_url']}@{candidate['commit_sha']}:{candidate['file_path']}"],
   "unverified",
  )
  return {"candidate": candidate, "memory_record": memory_record}
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
 """Return task counts, startup recovery snapshot, and bounded supervisor capability status."""
 status = agent_supervisor_status()
 status["startup_recovery"] = getattr(
  app.state, "task_startup_recovery",
  {"status": "not_run", "requeued_interrupted_count": 0},
 )
 return status


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

@app.post("/api/analytical-agent-tasks/{task_id}/retry")
def analytical_agent_retry_task(task_id: str):
 """Create one fresh queued retry for a failed task; dispatch remains explicit."""
 try:
  result = retry_failed_research_task(task_id)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 if result is None:
  raise HTTPException(status_code=404, detail="Analytical-agent task not found")
 return result

@app.post("/api/analytical-agent-tasks/{task_id}/cancel")
def analytical_agent_cancel_task(task_id: str):
 """Cancel a task only if it is still queued; running work is not interrupted."""
 try:
  result = cancel_queued_research_task(task_id)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 if result is None:
  raise HTTPException(status_code=404, detail="Analytical-agent task not found")
 return result

@app.get("/api/analytical-agent-tasks/{task_id}")
def analytical_agent_task_detail(task_id: str):
 """Retrieve one persisted analytical-agent task and its result."""
 record = get_research_task(task_id)
 if record is None:
  raise HTTPException(status_code=404, detail="Analytical-agent task not found")
 return record

@app.get("/api/analytical-agent-tasks/{task_id}/quality-evaluation")
def analytical_agent_task_quality_evaluation(task_id: str):
 """Retrieve a persisted structural traceability evaluation for one task."""
 record = get_task_quality_evaluation(task_id)
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




@app.post("/api/research/social-feeds")
async def research_social_feeds(request: SocialResearchRequest):
 """Fetch configured public Reddit RSS feeds for source-linked research only.

 This endpoint intentionally limits hosts and paths to public Reddit RSS
 feeds to reduce SSRF risk. It does not access private posts or provide
 trading recommendations.
 """
 configured = {}
 for feed in request.feeds:
  try:
   parsed = urlparse(feed.feed_url)
   port = parsed.port
  except ValueError as exc:
   raise HTTPException(status_code=400, detail="Feed URL is malformed") from exc
  host = (parsed.hostname or "").lower()
  if parsed.scheme != "https" or host not in {"reddit.com", "www.reddit.com"}:
   raise HTTPException(status_code=400, detail="Only HTTPS public Reddit RSS URLs are allowed")
  if parsed.username or parsed.password or port not in (None, 443):
   raise HTTPException(status_code=400, detail="Feed URL must not include credentials or a nonstandard port")
  if parsed.query or parsed.fragment:
   raise HTTPException(status_code=400, detail="Feed URL must not include query parameters or fragments")
  if not parsed.path.endswith(".rss") or not (
   parsed.path.startswith("/r/") or parsed.path.startswith("/user/")
  ):
   raise HTTPException(status_code=400, detail="Feed path must be a public Reddit subreddit or user RSS path")
  if feed.source in configured:
   raise HTTPException(status_code=400, detail="Feed source labels must be unique")
  configured[feed.source] = feed.feed_url
 result = await social_sources.ingest_public_social_feeds(
  configured, concurrency=request.concurrency
 )
 result["mode"] = "public_social_research"
 result["financial_advice"] = False
 result["execution"] = "disabled"
 return result

@app.post("/api/research/evidence/merge")
def merge_news_social_evidence(request: EvidenceMergeRequest):
 """Merge supplied news and social metadata into a common evidence schema."""
 try:
  return social_sources.merge_research_evidence(
   request.news_items, request.social_items
  )
 except (TypeError, ValueError) as exc:
  raise HTTPException(status_code=400, detail="Evidence must be JSON-compatible records") from exc


@app.post("/api/research/evidence/report")
def research_evidence_report(request: EvidenceReportRequest):
 """Return normalized evidence review plus shared-core synthesis."""
 try:
  evidence = social_sources.merge_research_evidence(
   request.news_items, request.social_items
  )
  synthesis = synthesize_research({
   "research_type": "evidence_review_report",
   "topic": request.topic,
   "evidence_report": evidence,
   "agent_context": (
    "Analyze the supplied evidence review report for the requested topic. "
    "Explain provenance gaps and manual cross-check candidates. Distinguish "
    "source metadata from credibility. Matching titles are not proof of "
    "corroboration. Do not infer consensus, contradiction, or truth from "
    "repetition or sentiment. State unknowns and keep source links available. "
    "Research only; no trading recommendations or execution."
   ),
  })
 except IntelligenceCoreError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 except (TypeError, ValueError) as exc:
  raise HTTPException(status_code=400, detail="Evidence must be JSON-compatible records") from exc
 return {
  "mode": "evidence_review_research",
  "topic": request.topic,
  "evidence_report": evidence,
  "synthesis": synthesis,
  "execution": "disabled",
  "financial_advice": False,
 }


@app.post("/api/research/social-feeds/synthesize")
async def research_social_feeds_synthesize(request: SocialResearchRequest):
 """Fetch allowlisted public Reddit RSS metadata, then optionally synthesize it.

 Social posts are untrusted research inputs. The shared core receives source links
 and metadata only; it does not make forecasts or trading recommendations.
 """
 evidence = await research_social_feeds(request)
 try:
  synthesis = synthesize_research({
   "research_type": "public_social_discussion",
   "coverage": evidence.get("coverage"),
   "source_results": evidence.get("source_results", []),
   "items": evidence.get("items", []),
   "agent_context": (
    "Describe recurring discussion themes, disagreement, evidence gaps, and "
    "source coverage. Treat posts as unverified claims. Do not infer market "
    "direction, price targets, trading setups, or recommendations."
   ),
  })
 except IntelligenceCoreError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
 return {
  "mode": "public_social_research",
  "evidence": evidence,
  "synthesis": synthesis,
  "execution": "disabled",
  "financial_advice": False,
 }


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


@app.get("/api/market-data/yahoo")
async def fetch_yahoo_historical_data(
 symbol: str,
 interval: str = "1d",
 limit: int = 100,
):
 """Fetch best-effort Yahoo historical bars, persist with provenance, and return normalized data.

 This community-facing endpoint is historical research only. Yahoo's chart endpoint
 is unofficial/best-effort and subject to upstream availability and terms.
 """
 if not symbol.strip() or len(symbol.strip()) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in {"15m", "1h", "4h", "1d"}:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 1 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
 try:
  batch = await YahooFinanceAdapter().get_bars(symbol, interval, limit)
  storage = market_store.store_batch(batch)
 except (ValueError, RuntimeError) as exc:
  raise HTTPException(status_code=502, detail=f"Historical provider unavailable or returned invalid data: {exc}") from exc
 return {
  "mode": "historical_research_ingestion",
  "symbol": batch.symbol, "interval": batch.interval,
  "source": batch.source, "status": batch.status.value,
  "retrieved_at": batch.retrieved_at.isoformat(),
  "observation_count": len(batch.bars),
  "storage": storage,
  "bars": [bar.model_dump(mode="json") for bar in batch.bars],
  "execution": "disabled",
  "warnings": batch.warnings + [
   "Provider endpoint is unofficial and may change or restrict access.",
   "Historical data only; no live trading, order routing, or buy/sell recommendation.",
  ],
 }


@app.post("/api/research/autonomous-stored")
async def autonomous_research_stored(
 symbol: str,
 interval: str = "1d",
 limit: int = 500,
):
 """Run descriptive chart research on one locally stored source/status dataset.

 Stored data is not assumed live. This endpoint refuses mixed-source/status
 records instead of silently blending different data provenance.
 """
 if not symbol.strip() or len(symbol) > 32:
  raise HTTPException(status_code=400, detail="symbol must contain 1 to 32 characters")
 if interval not in SUPPORTED_INTERVALS:
  raise HTTPException(status_code=400, detail="interval must be one of 15m,1h,4h,1d")
 if limit < 2 or limit > 5000:
  raise HTTPException(status_code=400, detail="limit must be between 2 and 5000")

 stored = market_store.get_bars(symbol, interval, limit)
 observations = stored.get("bars", [])
 if len(observations) < 2:
  raise HTTPException(status_code=404, detail="At least two stored bars are required")
 sources = {str(row.get("source", "")).strip() for row in observations}
 statuses = {str(row.get("status", "")).strip() for row in observations}
 if len(sources) != 1 or len(statuses) != 1 or not next(iter(sources), ""):
  raise HTTPException(status_code=409, detail={
   "error": "mixed_or_missing_provenance",
   "message": "Stored observations include multiple sources or statuses. Filter by provenance before research.",
   "sources": sorted(sources), "statuses": sorted(statuses),
  })
 source = next(iter(sources))
 status_value = next(iter(statuses))
 timestamps = [row["timestamp"] for row in observations]
 if len(timestamps) != len(set(timestamps)):
  raise HTTPException(status_code=409, detail={
   "error": "duplicate_timestamps",
   "message": "Stored source contains duplicate timestamps; resolve them before chart research.",
  })
 try:
  batch = MarketDataBatch(
   symbol=symbol.strip().upper(), interval=interval,
   status=status_value, source=source,
   retrieved_at=datetime.fromisoformat(stored["retrieved_at"]),
   bars=[{
    "timestamp": row["timestamp"], "open": row["open"],
    "high": row["high"], "low": row["low"],
    "close": row["close"], "volume": row["volume"],
   } for row in observations],
   warnings=[
    "Research uses locally stored observations, not a live feed.",
    "Source/status metadata are preserved; stored-data freshness and provider authenticity are not guaranteed.",
   ],
  )
  chart_history = {
   "symbol": batch.symbol, "interval": batch.interval,
   "bars": [{
    **bar.model_dump(mode="json"),
    "source": batch.source, "status": batch.status.value,
    "retrieved_at": batch.retrieved_at.isoformat(),
   } for bar in batch.bars],
  }
  report = build_chart_report(chart_history)
 except (ValueError, TypeError, KeyError) as exc:
  raise HTTPException(status_code=422, detail=f"Stored bars failed validation: {type(exc).__name__}") from exc
 return {
  "mode": "stored_descriptive_chart_research",
  "symbol": batch.symbol, "interval": batch.interval,
  "source": batch.source, "status": batch.status.value,
  "retrieved_at": batch.retrieved_at.isoformat(),
  "observation_count": len(batch.bars),
  "chart_report": report,
  "execution": "disabled",
  "limitations": [
   "This endpoint performs descriptive research only.",
   "Stored observations may be stale; retrieval metadata is not a freshness guarantee.",
   "No live trading, orders, financial advice, or buy/sell recommendations.",
  ],
 }


@app.post("/api/research/autonomous-fixture")
async def autonomous_research_fixture(request: AutonomousResearchFixtureRequest):
 """Run discovery-to-chart analysis with synthetic fixtures for integration tests only."""
 try:
  candidates = [
   MarketCandidate(
    symbol=item.symbol, venue=item.venue, asset_class=item.asset_class,
    source=item.source, observed_at=item.observed_at.isoformat(),
    data_available=item.data_available, data_quality=item.data_quality,
    activity=item.activity, volatility=item.volatility,
    news_attention=item.news_attention, social_attention=item.social_attention,
    timeframes=tuple(item.timeframes), notes=tuple(item.notes),
   )
   for item in request.candidates
  ]
  return await run_autonomous_research(
   candidates, SyntheticFixtureAdapter(),
   research_limit=request.research_limit, bars_limit=request.bars_limit,
   intervals=("1d",), use_shared_ai=request.use_shared_ai,
  )
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
  result["skill_protocols"] = [
   protocol for skill_id in request.skill_ids
   if (protocol := build_skill_protocol(skill_id)) is not None
  ]
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



@app.post("/api/research/quality-evaluate")
def evaluate_research_quality(request: ResearchQualityEvaluationRequest):
 """Evaluate source-reference coverage for a supplied research draft.

 This is a structural traceability check only; it does not validate truth,
 source authenticity, claim entailment, or forecast accuracy.
 """
 try:
  return evaluate_research_draft(
   draft=request.draft, claims=request.claims,
   source_registry=request.source_registry, baseline=request.baseline,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/evidence-audit")
def research_evidence_audit(request: ResearchEvidenceAuditRequest):
 """Audit source grouping and explicit claim-stance disagreements for human review."""
 try:
  return audit_evidence(
   claims=request.claims,
   source_registry=request.source_registry,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.post("/api/research/benchmark")
def run_research_benchmark(request: ResearchBenchmarkRequest):
 """Run a bounded deterministic benchmark using caller-supplied offline fixtures only."""
 try:
  return run_offline_research_benchmark(
   request.cases, baseline=request.baseline,
   regression_threshold=request.regression_threshold,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/research/synthesis/citation-audit")
def audit_research_synthesis_citations(request: ResearchCitationAuditRequest):
 """Check claim citation IDs and quoted excerpts against supplied source text."""
 try:
  return audit_claim_citations(
   claims=request.claims, source_registry=request.source_registry,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/synthesis/prepare-review")
def prepare_research_synthesis_review(request: ResearchQualityEvaluationRequest):
 """Prepare an evidence-aware synthesis review packet; never auto-approve."""
 try:
  return build_synthesis_review_packet(
   draft=request.draft, claims=request.claims,
   source_registry=request.source_registry,
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


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
  if request.claim_review_checklist is not None:
   submitted = request.claim_review_checklist
   if len(submitted) != len(request.claims):
    raise ValueError("claim_review_checklist must contain exactly one entry per claim.")
   for index, item in enumerate(submitted):
    if not isinstance(item, dict) or item.get("claim_index", index) != index:
     raise ValueError("Checklist claim_index values must match the corresponding claim order.")
    if "claim_text" in item and item["claim_text"] != request.claims[index].get("text"):
     raise ValueError("Checklist claim_text must match the corresponding claim.")
    if "source_refs" in item and item["source_refs"] != request.claims[index].get("source_refs", []):
     raise ValueError("Checklist source_refs must match the corresponding claim.")
   validated = validate_claim_review_checklist(submitted)
   review["claim_review_checklist"] = validated
  return workspace.save_synthesis_review(review)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/research/synthesis/reviews")
def list_research_synthesis_reviews(limit: int = 50, status: str | None = None,
                                    reviewer: str | None = None):
 """List metadata only, filtered by exact status and reviewer label."""
 try:
  return {"reviews": workspace.list_synthesis_reviews(limit, status=status, reviewer=reviewer)}
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/synthesis/reviews/summary")
def summarize_research_synthesis_reviews(status: str | None = None,
                                         reviewer: str | None = None):
 """Return metadata-only counts, optionally filtered by exact status/reviewer label."""
 try:
  return workspace.synthesis_review_summary(status=status, reviewer=reviewer)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/synthesis/reviews/{review_id}")
def get_research_synthesis_review(review_id: str):
 """Retrieve one saved review and report its SHA-256 integrity check."""
 result = workspace.get_synthesis_review(review_id)
 if result is None:
  raise HTTPException(status_code=404, detail="Synthesis review not found")
 return result


@app.post("/api/research/orchestrate")
def orchestrate_research_request(request: ResearchOrchestrationRequest):
 """Coordinate specialist workers through the shared deterministic intelligence core."""
 try:
  return orchestrate_research(
   nodes=request.nodes, edges=request.edges, inputs=request.inputs,
   max_workers=request.max_workers, max_retries=request.max_retries,
   evidence_claims=request.evidence_claims, source_registry=request.source_registry,
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


@app.get("/api/workers/{worker_id}/research-quality-dashboard")
def get_worker_research_quality_dashboard(worker_id: str, limit: int = 100):
 """Combine staging gate, paired regression, provenance, and repeatability summaries."""
 try:
  return summarize_research_quality_dashboard(worker_id, limit)
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workers/{worker_id}/staging-experiments/audit-export")
def export_worker_staging_audit(worker_id: str, limit: int = 100):
 """Return a consolidated JSON audit bundle for offline staging records.

 This is an export of existing records and summaries only; it does not rerun
 benchmarks, validate declared provenance, train, deploy, or trade.
 """
 if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
  raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
 try:
  from .staging_experiments import list_staging_experiments
  bundle = {
   "worker_id": worker_id,
   "export_type": "offline_staging_audit_bundle",
   "dashboard": summarize_research_quality_dashboard(worker_id, limit),
   "provenance": summarize_staging_provenance(worker_id, limit),
   "experiment_records": list_staging_experiments(worker_id, limit)["experiments"],
   "limitations": [
    "Dataset metadata is caller-declared and not authenticated.",
    "Fixture traceability metrics do not measure factual accuracy or market forecasting skill.",
    "No model training, deployment, or trading is performed by this export.",
   ],
  }
  # Hash the canonical bundle before adding the integrity metadata. This detects
  # accidental export changes; it does not authenticate the data or its sources.
  from .audit_integrity import build_integrity_metadata
  bundle["integrity"] = build_integrity_metadata(bundle)
  encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
  safe_worker_id = "".join(ch for ch in worker_id if ch.isalnum() or ch in "-_")[:80] or "worker"
  return Response(
   content=encoded,
   media_type="application/json",
   headers={"Content-Disposition": f'attachment; filename="market-mind-staging-audit-{safe_worker_id}.json"'},
  )
 except ValueError as exc:
  raise HTTPException(status_code=400, detail=str(exc)) from exc
