from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
from .workflow import NODE_TYPES, execute_workflow
from .workers import list_workers

app = FastAPI(title="MARKET-MIND-AI API", version="0.1.0", description="Visual multi-agent market research workflow engine")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class WorkflowRequest(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "market-mind-ai", "mode": "research-only", "execution_trading": False}

@app.get("/api/nodes")
def nodes():
    return {"nodes": list(NODE_TYPES.values())}

@app.get("/api/workers")
def workers(department: str | None = None, limit: int = 550):
    items = list_workers()
    if department:
        items = [w for w in items if w["department"] == department]
    return {"count": len(items[:max(1, min(limit, 550))]), "workers": items[:max(1, min(limit, 550))]}

@app.post("/api/workflows/execute")
def run_workflow(request: WorkflowRequest):
    try:
        return execute_workflow(request.nodes, request.edges, request.inputs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}") from exc
