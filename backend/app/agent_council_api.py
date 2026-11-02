"""HTTP API routes for bounded specialist AI agent council research."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from .agent_council import run_agent_council, run_agent_batch
from .agent_council_review import review_council_outputs

router = APIRouter()


class AgentCouncilRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=1, max_length=8)
    brief: str = Field(min_length=1, max_length=4000)
    data: dict[str, Any] | list[Any] | None = None


class AgentBatchRequest(BaseModel):\n    agent_ids: list[str] = Field(min_length=1, max_length=550)\n    brief: str = Field(min_length=1, max_length=4000)\n    data: dict[str, Any] | list[Any] | None = None\n\n\nclass AgentCouncilReviewRequest(BaseModel):
    council_result: dict[str, Any]


@router.post("/api/agent-council/run")
def run_council(request: AgentCouncilRequest):
    """Run up to eight specialist contexts against user-supplied research data."""
    try:
        return run_agent_council(request.agent_ids, request.brief, request.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/agent-council/review")
def review_council(request: AgentCouncilReviewRequest):
    """Review council output fingerprints without asserting semantic consensus."""
    try:
        return review_council_outputs(request.council_result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/agent-council/batch")
def run_agent_batch_api(request: AgentBatchRequest):
    """Run a bounded research task across selected registered agents (up to 550)."""
    try:
        return run_agent_batch(request.agent_ids, request.brief, request.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
