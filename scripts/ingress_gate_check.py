#!/usr/bin/env python3
"""Local validation of the six public-ingress gates.

This script does NOT deploy or enable public ingress. It checks only local,
secret-free evidence and prints a JSON report. Every public gate stays BLOCKED
until an external operator supplies genuine evidence; the local checks below
are prerequisites, not approvals.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = Path("/home/jovyan/.market-mind-ops")
GATES = ("G1", "G2", "G3", "G4", "G5", "G6")


def preflight() -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "config_preflight.py"), "--root", str(ROOT)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {"status": "unreadable", "checks": [], "failed": ["unreadable_report"]}


def check_status(report: dict, check_id: str) -> str | None:
    for entry in report.get("checks", []):
        if entry.get("id") == check_id:
            return entry.get("status")
    return None


def listeners() -> list[dict]:
    found = []
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        path = Path(name)
        if not path.is_file():
            continue
        for line in path.read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) > 3 and parts[3] == "0A":
                address, port_hex = parts[1].split(":")
                found.append({"ip": address, "port": int(port_hex, 16)})
    return found


def bundle_outcome(check_id: str) -> str:
    path = ROOT / "docs" / "external-evidence" / f"{check_id}.json"
    if not path.is_file():
        return "missing"
    try:
        return json.loads(path.read_text()).get("outcome", "unknown")
    except ValueError:
        return "unreadable"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def report() -> dict:
    pre = preflight()
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(errors="replace")
    compose = (ROOT / "docker-compose.yml").read_text(errors="replace")
    stack_ports = [entry for entry in listeners() if entry["port"] in (8000, 8080)]
    internal = read_json(OPS / "internal-security-evidence.json")
    recovery = read_json(OPS / "container-recovery-evidence.json")
    inventory = ROOT / "docs" / "LICENSED-DATA-INVENTORY.md"
    attested = os.getenv("MARKET_MIND_ATTESTED_DATA_SOURCES", "").strip()

    gates = [
        {
            "id": "G1",
            "name": "TLS issuance/scan",
            "public_status": "BLOCKED",
            "local_validation": {
                "tls_template_present": (ROOT / "deploy" / "tls" / "nginx-tls.conf.example").is_file(),
                "preflight_tls_template": check_status(pre, "tls_template"),
            },
            "external_dependency": "CA-issued certificate and TLS/HSTS scan on reviewed host",
        },
        {
            "id": "G2",
            "name": "network segmentation",
            "public_status": "BLOCKED",
            "local_validation": {
                "stack_listeners": stack_ports,
                "backend_not_host_published": check_status(pre, "backend_not_host_published"),
                "published_ports_loopback": check_status(pre, "published_ports_loopback"),
                "compose_loopback_binding": "127.0.0.1:8080:8080" in compose,
            },
            "external_dependency": "host firewall/ACL/segmentation evidence",
        },
        {
            "id": "G3",
            "name": "ingress hardening",
            "public_status": "BLOCKED",
            "local_validation": {
                "limit_conn": "limit_conn" in nginx,
                "limit_req": "limit_req" in nginx,
                "csp_default_self": "default-src 'self'" in nginx,
                "preflight_ingress": check_status(pre, "ingress_limits_and_proto"),
            },
            "external_dependency": "deployed public ingress hardening verification",
        },
        {
            "id": "G4",
            "name": "independent security sign-off",
            "public_status": "BLOCKED",
            "local_validation": {
                "internal_audit_passed": internal.get("passed"),
                "EXT_03_outcome": bundle_outcome("EXT-03"),
            },
            "external_dependency": "independent reviewer, signed report and go/no-go",
        },
        {
            "id": "G5",
            "name": "licensed market-data/legal review",
            "public_status": "BLOCKED",
            "local_validation": {
                "inventory_present": inventory.is_file(),
                "attested_sources_configured": bool(attested),
            },
            "external_dependency": "licensed provider, archived terms and written legal approval",
        },
        {
            "id": "G6",
            "name": "host recovery drill",
            "public_status": "BLOCKED",
            "local_validation": {
                "non_privileged_drill_passed": recovery.get("passed"),
                "EXT_02_outcome": bundle_outcome("EXT-02"),
            },
            "external_dependency": "root/systemd/Docker host restart and volume drill",
        },
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_ingress_enabled": False,
        "gates": gates,
        "passed": sum(1 for gate in gates if gate["public_status"] == "PASS"),
        "total": len(gates),
        "scope": "local prerequisites only; no public ingress enabled or approved",
    }


def main() -> int:
    print(json.dumps(report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
