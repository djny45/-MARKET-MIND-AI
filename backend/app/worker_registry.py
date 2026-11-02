"""Versioned specialist AI-agent registry manifest and deterministic integrity evaluation."""
import hashlib
import json

from .workers import DEPARTMENTS, list_workers
from .skill_catalog import list_skills

REGISTRY_VERSION = "1.0.0"
EXPECTED_WORKER_COUNT = 550
EXPECTED_CORE = "shared_central_intelligence"


def evaluate_registry() -> dict:
    workers = list_workers()
    ids = [worker.get("id") for worker in workers]
    expected_ids = [f"worker_{index:03d}" for index in range(1, EXPECTED_WORKER_COUNT + 1)]
    errors = []
    if len(workers) != EXPECTED_WORKER_COUNT:
        errors.append("agent_count_mismatch")
    if ids != expected_ids:
        errors.append("agent_ids_not_contiguous_or_ordered")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_agent_ids")
    if any(worker.get("model") != EXPECTED_CORE for worker in workers):
        errors.append("agent_core_mismatch")
    if any(worker.get("department") not in DEPARTMENTS for worker in workers):
        errors.append("unknown_department")
    allowed_skill_ids = {skill["id"] for skill in list_skills()}
    if any(skill_id not in allowed_skill_ids for worker in workers for skill_id in worker.get("skill_refs", [])):
        errors.append("unknown_skill_reference")
    required = {"id", "name", "department", "specialty", "kind", "model",
                "memory_namespace", "skill_refs", "status"}
    if any(not required.issubset(worker) for worker in workers):
        errors.append("agent_profile_missing_required_fields")
    canonical = json.dumps(workers, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    counts = {department: sum(worker["department"] == department for worker in workers)
              for department in DEPARTMENTS}
    return {
        "registry_version": REGISTRY_VERSION,
        "agent_count": len(workers),
        "worker_count": len(workers),  # legacy API compatibility
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
        "worker_count": evaluation["agent_count"],  # legacy API compatibility
        "department_count": evaluation["department_count"],
        "profile_digest_sha256": evaluation["profile_digest_sha256"],
        "valid": evaluation["valid"],
        "shared_intelligence_core": EXPECTED_CORE,
    }
