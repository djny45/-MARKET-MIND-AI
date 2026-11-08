"""Build a source-linked review bundle from existing open-source evidence records.

This is a read-only assembly step. It does not validate factual/legal claims,
execute source code, train models, or approve/publish research skills.
"""
from __future__ import annotations

from typing import Any


def build_review_bundle(candidate_record: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(candidate_record, dict):
        raise ValueError("candidate_record must be an object")
    candidate_id = candidate_record.get("memory_id")
    candidate = candidate_record.get("content")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate memory ID is missing")
    if not isinstance(candidate, dict) or candidate.get("record_type") != "open_source_learning_candidate":
        raise ValueError("memory record is not an open-source learning candidate")
    if not isinstance(records, list):
        raise ValueError("records must be a list")

    related = []
    for item in records:
        content = item.get("content") if isinstance(item, dict) else None
        if not isinstance(content, dict):
            continue
        if (content.get("source_memory_id") == candidate_id
                and content.get("record_type") == "github_research_chunk_manifest"):
            related.append(("chunk_manifest", item))
        if (content.get("candidate_memory_id") == candidate_id
                and content.get("record_type") == "github_research_evidence_quality"):
            related.append(("provenance_score", item))
        if (content.get("record_type") == "pinned_github_license_evidence"
                and content.get("repository_url") == candidate.get("repository_url")
                and content.get("commit_sha") == candidate.get("commit_sha")):
            related.append(("license_evidence", item))

    evidence = {kind: item for kind, item in related}
    missing = [kind for kind in ("chunk_manifest", "provenance_score", "license_evidence")
               if kind not in evidence]
    score_content = evidence.get("provenance_score", {}).get("content", {})
    score = score_content.get("score") if isinstance(score_content, dict) else None
    license_content = evidence.get("license_evidence", {}).get("content", {})
    license_found = (isinstance(license_content, dict)
                     and license_content.get("license_file_found") is True)
    manifest_content = evidence.get("chunk_manifest", {}).get("content", {})
    manifest_matches = (isinstance(manifest_content, dict)
                        and manifest_content.get("source_sha256") == candidate.get("content_sha256")
                        and manifest_content.get("source_memory_id") == candidate_id)

    if "chunk_manifest" in evidence and not manifest_matches:
        missing.append("matching_chunk_manifest")
    if "license_evidence" in evidence and not license_found:
        missing.append("license_file_found")
    if "provenance_score" in evidence and (
            isinstance(score, bool) or not isinstance(score, int) or score < 0 or score > 100):
        missing.append("valid_provenance_score")

    return {
        "candidate_memory_id": candidate_id,
        "source": {
            "repository_url": candidate.get("repository_url"),
            "commit_sha": candidate.get("commit_sha"),
            "file_path": candidate.get("file_path"),
            "content_sha256": candidate.get("content_sha256"),
        },
        "evidence_memory_ids": {
            kind: item.get("memory_id") for kind, item in evidence.items()
        },
        "provenance_score": score,
        "license_file_found": license_found,
        "chunk_manifest_matches_source": bool(manifest_matches),
        "missing_evidence": sorted(set(missing)),
        "review_status": "ready_for_human_review" if not missing else "evidence_incomplete",
        "human_review_required": True,
        "automatic_promotion": False,
        "execution_allowed": False,
        "model_training": False,
        "note": "Bundle completeness is not legal approval, factual verification, or permission to execute/promote code.",
    }
