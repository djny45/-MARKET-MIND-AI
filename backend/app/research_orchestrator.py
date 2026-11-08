"""Central research orchestrator over the single deterministic workflow core.

This first orchestration layer coordinates existing analytical handlers. It does
not invoke LLMs, create autonomous processes, fetch live data, or place orders.
"""
from .workflow import execute_workflow
from .worker_registry import evaluate_registry
from .intelligence_core import synthesize_research
from .research_evidence_audit import audit_evidence


def orchestrate_research(nodes, edges, inputs, max_workers=1, max_retries=0, evidence_claims=None, source_registry=None):
    registry = evaluate_registry()
    if not registry["valid"]:
        raise ValueError("Worker registry integrity check failed.")
    execution = execute_workflow(
        nodes=nodes,
        edges=edges,
        inputs=inputs,
        max_workers=max_workers,
        max_retries=max_retries,
    )
    worker_results = []
    for task in execution.get("tasks", []):
        node_id = task.get("node_id")
        status = task.get("status")
        worker_results.append({
            "task_id": task.get("task_id"),
            "node_id": node_id,
            "node_type": task.get("node_type"),
            "worker_id": task.get("assigned_worker_id"),
            "worker_name": task.get("assigned_worker"),
            "department": task.get("worker_department"),
            "specialty": task.get("worker_specialty"),
            "status": status,
            "result": execution.get("results", {}).get(node_id) if status == "completed" else None,
            "contract_version": (task.get("worker_contract") or {}).get("contract_version"),
            "evidence_status": "source_provenance_not_attached",
        })
    completed = [item for item in worker_results if item["status"] == "completed"]
    failed = [item for item in worker_results if item["status"] in ("failed", "skipped")]
    report = {
        "title": "Central research orchestration report",
        "summary": {
            "tasks_total": len(worker_results),
            "tasks_completed": len(completed),
            "tasks_failed_or_skipped": len(failed),
            "departments_represented": sorted({item["department"] for item in completed if item["department"]}),
        },
        "findings": [
            {
                "worker_id": item["worker_id"],
                "worker_name": item["worker_name"],
                "department": item["department"],
                "node_type": item["node_type"],
                "result": item["result"],
                "evidence_status": item["evidence_status"],
            }
            for item in completed
        ],
        "limitations": [
            "This report contains deterministic analytical outputs, not model-generated conclusions.",
            "Source provenance is not attached unless supplied by an upstream data provider.",
            "No live data retrieval, investment recommendation, or brokerage execution is performed.",
        ],
    }
    evidence_audit = audit_evidence(
        claims=evidence_claims or [],
        source_registry=source_registry or [],
    )
    report["evidence_audit"] = evidence_audit
    report["limitations"].append(
        "Evidence audit checks supplied identifiers and declared source grouping only; it does not verify source authenticity or claim entailment."
    )
    synthesis = synthesize_research(report)
    return {
        "orchestration_status": "completed" if not failed else "completed_with_errors",
        "intelligence_core": registry["shared_intelligence_core"],
        "registry_version": registry["registry_version"],
        "registry_digest_sha256": registry["profile_digest_sha256"],
        "execution": execution,
        "worker_results": worker_results,
        "report": report,
        "model_synthesis": synthesis,
        "capabilities": {
            "logical_worker_coordination": True,
            "shared_core": True,
            "llm_inference": False,
            "autonomous_learning": False,
            "broker_execution": False,
        },
    }
