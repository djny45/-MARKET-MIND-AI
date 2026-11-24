#!/usr/bin/env python3
"""Fail-closed intake for the three external acceptance checks.

This tool prepares evidence templates, validates *operator-supplied* evidence
bundles and audits the acceptance inventory. It never executes EXT-01/02/03,
never contacts external systems, and never changes an acceptance status.

A structurally complete bundle is NOT an approval: the go/no-go decision stays
with the external operator named in the access-request document. Mock, fake,
moto or simulated runs cannot produce a complete bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from dr_common import REPO_ROOT, iso_now

SPECS: dict[str, dict] = {
    "EXT-01": {
        "acceptance_id": "ACC-029",
        "title": "Real cloud S3 restore using authorized infrastructure",
        "evidence": "docs/S3-VERIFICATION-PACKAGE.md",
        "operator": "Cloud infrastructure owner (IAM) + private database host owner",
        "artifacts": (
            "describe-config.json", "backup-manifest.json", "upload-result.json",
            "download-result.json", "restore-report.json", "recovery-report.json",
            "sha256-parity.txt",
        ),
        "checks": (
            "sha256_parity", "restore_comparison_matched", "database_integrity_ok",
            "no_secrets_in_output", "isolated_target_only",
        ),
    },
    "EXT-02": {
        "acceptance_id": "ACC-030",
        "title": "Real host service install, restart and recovery drill",
        "evidence": "docs/HOST-RECOVERY-PROCEDURE.md",
        "operator": "Host/system administrator with root plus the service owner",
        "artifacts": (
            "host-identity.txt", "systemctl-status.txt", "list-timers.txt",
            "restart-report.json", "recovery-report.json", "journal-excerpt.txt",
            "volume-drill-result.json",
        ),
        "checks": (
            "timer_active", "backup_freshness_ok", "stale_locks_removed",
            "task_requeued_once", "database_integrity_ok", "volume_comparison_matched",
            "disposable_volume_removed",
        ),
    },
    "EXT-03": {
        "acceptance_id": "ACC-031",
        "title": "Independent security review with formal sign-off",
        "evidence": "docs/SECURITY-REVIEW-PACKAGE.md",
        "operator": "Independent security lead / penetration-test provider + repository owner",
        "artifacts": (
            "rules-of-engagement.txt", "scope.txt", "findings.json",
            "scanner-output.txt", "tls-scan.txt", "signed-report.pdf",
            "sign-off.txt",
        ),
        "checks": (
            "scope_fully_executed", "no_open_critical_or_high", "medium_findings_accepted",
            "remediations_retested", "signed_go_decision", "independent_reviewer",
        ),
    },
}

REQUIRED_FIELDS = (
    "bundle_id", "check_id", "acceptance_id", "outcome", "environment",
    "operator_identity", "owner_identity", "executed_at", "procedure",
    "artifacts", "checks", "notes",
)
MOCK_MARKERS = ("mock", "fake", "moto", "simulat", "stub", "dry-run", "dry_run", "sandbox")
SECRET_PATTERNS = (
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("s3_secret_assignment", re.compile(r"MARKET_MIND_S3_SECRET_KEY\s*=\s*(?!\[REDACTED\]|<|\")([^\s]{6,})")),
    ("bearer_token", re.compile(r"\bBearer\s+eyJ[A-Za-z0-9_-]{10,}\b")),
)


def _spec(check_id: str) -> dict:
    try:
        return SPECS[check_id]
    except KeyError:
        raise SystemExit(f"unknown check id: {check_id}; expected one of {', '.join(SPECS)}")


def build_template(check_id: str) -> dict:
    spec = _spec(check_id)
    return {
        "bundle_id": f"{check_id}-<unique-id>",
        "check_id": check_id,
        "acceptance_id": spec["acceptance_id"],
        "outcome": "pending",
        "environment": "",
        "operator_identity": "",
        "owner_identity": "",
        "executed_at": "",
        "procedure": spec["evidence"],
        "artifacts": {name: {"path": name, "sha256": ""} for name in spec["artifacts"]},
        "checks": {name: False for name in spec["checks"]},
        "notes": "Complete this bundle only from a real authorized drill; never from mock evidence.",
        "generated_at": iso_now(),
        "external_approval": "not_claimed",
    }


def _secret_findings(raw: str) -> list[str]:
    return sorted({name for name, pattern in SECRET_PATTERNS if pattern.search(raw)})


def validate_bundle(path: Path, root: Path = REPO_ROOT) -> dict:
    """Structurally validate an operator-supplied bundle. Never approves it."""
    findings: list[str] = []
    bundle_id = None
    check_id = None
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "invalid", "closure_allowed": False,
                "findings": [f"unreadable bundle: {type(exc).__name__}"]}
    if not isinstance(bundle, dict):
        return {"status": "invalid", "closure_allowed": False,
                "findings": ["bundle root must be a JSON object"]}

    bundle_id = str(bundle.get("bundle_id", ""))
    check_id = str(bundle.get("check_id", ""))
    for field in REQUIRED_FIELDS:
        if field not in bundle:
            findings.append(f"missing field: {field}")
        elif bundle[field] in ("", None, {}, []):
            findings.append(f"empty field: {field}")
    secrets = _secret_findings(path.read_text(encoding="utf-8"))
    findings.extend(f"secret-looking value: {name}" for name in secrets)

    if check_id in SPECS:
        spec = SPECS[check_id]
        if bundle.get("acceptance_id") != spec["acceptance_id"]:
            findings.append("acceptance_id does not match check_id")
        artifacts = bundle.get("artifacts")
        if isinstance(artifacts, dict):
            for name in spec["artifacts"]:
                record = artifacts.get(name)
                if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
                    findings.append(f"artifact not recorded: {name}")
                    continue
                artifact = (path.parent / str(record["path"])).resolve()
                if not artifact.is_file():
                    findings.append(f"artifact missing: {name}")
                    continue
                actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if actual != str(record["sha256"]).strip().lower():
                    findings.append(f"artifact hash mismatch: {name}")
        checks = bundle.get("checks")
        if isinstance(checks, dict):
            for name in spec["checks"]:
                if checks.get(name) is not True:
                    findings.append(f"check not passed: {name}")
        environment = str(bundle.get("environment", "")).lower()
        for marker in MOCK_MARKERS:
            if marker in environment:
                findings.append(f"non-production environment marker: {marker}")
    else:
        findings.append(f"unknown check_id: {check_id}")

    if str(bundle.get("outcome", "")) != "passed":
        findings.append(f"outcome is {bundle.get('outcome')!r}, not 'passed'")
    if str(bundle.get("external_approval", "")) == "approved":
        findings.append("bundle cannot self-certify external approval")

    complete = not findings
    return {
        "status": "valid" if complete else "invalid",
        "bundle_id": bundle_id,
        "check_id": check_id,
        "acceptance_id": bundle.get("acceptance_id"),
        "evidence_complete": complete,
        "closure_allowed": complete,
        "external_approval": "not_claimed",
        "findings": findings,
        "note": "Structural completeness only; an external operator must still issue sign-off.",
    }


def audit_inventory(inventory: Path, evidence_root: Path, root: Path = REPO_ROOT) -> dict:
    data = json.loads(inventory.read_text(encoding="utf-8"))
    rows = list(data.get("acceptance_matrix", [])) + list(data.get("operations_matrix", []))
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    blocked = [row for row in rows if row["status"] == "blocked"]
    intake: list[dict] = []
    for row in blocked:
        check = next((key for key, spec in SPECS.items()
                      if spec["acceptance_id"] == row["id"]), None)
        bundle_path = evidence_root / f"{check}.json" if check else None
        result = None
        if bundle_path and bundle_path.is_file():
            result = validate_bundle(bundle_path, root)
        intake.append({
            "id": row["id"],
            "check_id": check,
            "evidence_bundle": str(bundle_path) if bundle_path else None,
            "bundle_present": bool(bundle_path and bundle_path.is_file()),
            "closure_allowed": bool(result and result["closure_allowed"]),
            "status": row["status"],  # never mutated by this tool
        })
    return {
        "inventory": str(inventory),
        "total_items": len(rows),
        "statuses": statuses,
        "verified": statuses.get("verified", 0),
        "blocked": len(blocked),
        "completion_percentage": round(100 * statuses.get("verified", 0) / len(rows), 1) if rows else 0,
        "intake": intake,
        "statuses_mutated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tpl = sub.add_parser("template", help="write a pending evidence template")
    tpl.add_argument("--id", choices=tuple(SPECS), required=True)
    tpl.add_argument("--output", type=Path, required=True)

    val = sub.add_parser("validate", help="validate an operator-supplied evidence bundle")
    val.add_argument("--bundle", type=Path, required=True)

    audit = sub.add_parser("audit", help="report inventory counts without changing statuses")
    audit.add_argument("--inventory", type=Path,
                       default=REPO_ROOT / "docs" / "acceptance-inventory.json")
    audit.add_argument("--evidence-root", type=Path,
                       default=REPO_ROOT / "docs" / "external-evidence")

    args = parser.parse_args(argv)
    if args.command == "template":
        target = args.output
        if target.exists():
            raise SystemExit(f"refusing to overwrite existing file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(build_template(args.id), indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        print(json.dumps({"status": "template_created", "check_id": args.id,
                          "path": str(target), "outcome": "pending"}, sort_keys=True))
        return 0
    if args.command == "validate":
        result = validate_bundle(args.bundle)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result["status"] == "valid" else 1
    result = audit_inventory(args.inventory, args.evidence_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
