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
    errors = []
    if not isinstance(workers, list):
        workers = []
        errors.append("agent_profiles_not_a_list")
    malformed_profiles = [
        index for index, worker in enumerate(workers)
        if not isinstance(worker, dict)
    ]
    if malformed_profiles:
        errors.append("agent_profile_not_an_object")
    profiles = [worker for worker in workers if isinstance(worker, dict)]

    ids = [worker.get("id") for worker in profiles]
    expected_ids = [f"worker_{index:03d}" for index in range(1, EXPECTED_WORKER_COUNT + 1)]
    if len(workers) != EXPECTED_WORKER_COUNT:
        errors.append("agent_count_mismatch")
    if ids != expected_ids:
        errors.append("agent_ids_not_contiguous_or_ordered")
    if len(set(item for item in ids if isinstance(item, str))) != len(ids):
        errors.append("duplicate_agent_ids")
    if any(worker.get("model") != EXPECTED_CORE for worker in profiles):
        errors.append("agent_core_mismatch")
    if any(worker.get("department") not in DEPARTMENTS for worker in profiles):
        errors.append("unknown_department")

    catalog_skills = list_skills()
    allowed_skill_ids = {
        skill.get("id") for skill in catalog_skills
        if isinstance(skill, dict) and isinstance(skill.get("id"), str)
    }
    malformed_skill_refs = any(
        not isinstance(worker.get("skill_refs", []), list)
        or any(not isinstance(skill_id, str) for skill_id in worker.get("skill_refs", []))
        for worker in profiles
    )
    if malformed_skill_refs:
        errors.append("invalid_worker_skill_references")
    all_skill_refs = []
    for worker in profiles:
        skill_refs = worker.get("skill_refs", [])
        if isinstance(skill_refs, list):
            all_skill_refs.extend(
                skill_id for skill_id in skill_refs if isinstance(skill_id, str)
            )
    if any(skill_id not in allowed_skill_ids for skill_id in all_skill_refs):
        errors.append("unknown_skill_reference")
    if any(
        len(worker.get("skill_refs", [])) != len(set(worker.get("skill_refs", [])))
        for worker in profiles
        if isinstance(worker.get("skill_refs", []), list)
        and all(isinstance(skill_id, str) for skill_id in worker.get("skill_refs", []))
    ):
        errors.append("duplicate_worker_skill_reference")
    pack_skill_ids = {
        skill["id"] for skill in catalog_skills
        if isinstance(skill, dict) and isinstance(skill.get("id"), str)
        and skill["id"].startswith("mm-skill-")
    }
    assigned_pack_skill_ids = {
        skill_id for skill_id in all_skill_refs if skill_id.startswith("mm-skill-")
    }
    missing_pack_skill_ids = sorted(pack_skill_ids - assigned_pack_skill_ids)
    if missing_pack_skill_ids:
        errors.append("unassigned_research_pack_skill")
    skill_ref_counts = {
        department: sum(
            len(worker.get("skill_refs", []))
            for worker in profiles
            if worker.get("department") == department
            and isinstance(worker.get("skill_refs", []), list)
        )
        for department in DEPARTMENTS
    }
    pack_skill_coverage = {
        "catalog_pack_skill_count": len(pack_skill_ids),
        "assigned_unique_pack_skill_count": len(assigned_pack_skill_ids & pack_skill_ids),
        "missing_pack_skill_ids": missing_pack_skill_ids,
        "coverage_ratio": round(len(assigned_pack_skill_ids & pack_skill_ids) / len(pack_skill_ids), 4) if pack_skill_ids else 1.0,
    }
    required = {"id", "name", "department", "specialty", "kind", "model",
                "memory_namespace", "skill_refs", "status"}
    if any(not required.issubset(worker) for worker in profiles):
        errors.append("agent_profile_missing_required_fields")
    canonical = json.dumps(workers, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    counts = {
        department: sum(worker.get("department") == department for worker in profiles)
        for department in DEPARTMENTS
    }
    return {
        "registry_version": REGISTRY_VERSION,
        "agent_count": len(workers),
        "worker_count": len(workers),
        "department_count": len(DEPARTMENTS),
        "department_counts": counts,
        "skill_reference_counts_by_department": skill_ref_counts,
        "research_pack_skill_coverage": pack_skill_coverage,
        "total_skill_reference_count": len(all_skill_refs),
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
