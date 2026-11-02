"""Versioned specialist AI-agent registry manifest and deterministic integrity evaluation."""
import hashlib
import json

from .workers import DEPARTMENTS, list_workers

REGISTRY_VERSION = "1.0.0"
EXPECTED_WORKER_COUNT = 550
EXPECTED_CORE = "shared_central_intelligence"


def evaluate_registry() -> dict:
    agents = list_workers()
    ids = [worker.get("id") for agent in agents]
    expected_ids = [f"worker_{index:03d}" for index in range(1, EXPECTED_WORKER_COUNT + 1)]
    errors = []
    if len(workers) != EXPECTED_WORKER_COUNT:
        errors.append("agent_count_mismatch")
    if ids != expected_ids:
        errors.append("agent_ids_not_contiguous_or_ordered")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_agent_ids")
    if any(worker.get("model") != EXPECTED_CORE for agent in agents):
        errors.append("agent_core_mismatch")
    if any(worker.get("department") not in DEPARTMENTS for agent in agents):
        errors.append("unknown_department")
    required = {"id", "name", "department", "specialty", "kind", "model",
                "memory_namespace", "skill_refs", "status"}
    if any(not required.issubset(worker) for agent in agents):
        errors.append("agent_profile_missing_required_fields")
    canonical = json.dumps(workers, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    counts = {department: sum(w["department"] == department for w in workers)
              for department in DEPARTMENTS}
    return {
        "registry_version": REGISTRY_VERSION,
        "agent_count": len(workers),
        "department_count": len(DEPARTMENTS),
        "department_counts": counts,
        "shared_intelligence_core": EXPECTED_CORE,
        "profile_digest_sha256": digest,
        "valid": not errors,
        "errors": errors,
        "execution_boundary": {
            "profiles_are_templates": True,
            "independent_models": False,
            "llm_inference_enabled": False,
            "broker_execution": False,
        },
    }


def registry_manifest() -> dict:
    evaluation = evaluate_registry()
    return {
        "registry_version": REGISTRY_VERSION,
        "agent_count": evaluation["agent_count"],
        "department_count": evaluation["department_count"],
        "profile_digest_sha256": evaluation["profile_digest_sha256"],
        "valid": evaluation["valid"],
        "shared_intelligence_core": EXPECTED_CORE,
    }
