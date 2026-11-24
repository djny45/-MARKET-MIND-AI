#!/usr/bin/env python3
"""Offline deployment configuration preflight (no Docker, nginx or secrets).

Checks the shipped TLS template, ingress configuration, Compose segmentation,
DR environment variables and deploy-check gates. Emits only check IDs/statuses;
no environment values, URLs or command strings are printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dr_common import validate_dr_environment


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _ports_in_block(lines: list[str]) -> list[str]:
    """Return every published-port entry from a Compose service block."""
    entries: list[str] = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ports:"):
            inline = stripped.split(":", 1)[1].strip()
            if inline:
                entries.extend(
                    token.strip().strip('"').strip("'")
                    for token in inline.strip("[]").split(",") if token.strip()
                )
            collecting = True
            continue
        if collecting:
            if stripped.startswith("- "):
                entries.append(stripped[2:].strip().strip('"').strip("'"))
            elif stripped:
                collecting = False
    return entries


def _compose_checks(text: str) -> list[dict]:
    results: list[dict] = []
    if not text:
        return [{"id": "compose_present", "status": "fail", "detail": "docker-compose.yml missing"}]
    results.append({"id": "compose_present", "status": "pass", "detail": "file found"})
    blocks: dict[str, list[str]] = {}
    current = None
    in_services = False
    for line in text.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if in_services and line and not line.startswith(" "):
            break
        if not in_services:
            continue
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip().rstrip(":")
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    expected = {"backend", "agent-supervisor", "frontend", "n8n"}
    results.append({
        "id": "compose_services_present",
        "status": "pass" if expected.issubset(blocks) else "fail",
        "detail": f"{len(blocks)} services found",
    })
    exposed = [
        name for name in ("backend", "agent-supervisor")
        if _ports_in_block(blocks.get(name, []))
        or any("network_mode: host" in line for line in blocks.get(name, []))
    ]
    results.append({
        "id": "backend_not_host_published",
        "status": "pass" if not exposed else "fail",
        "detail": "no host ports or host networking" if not exposed else ", ".join(exposed),
    })
    weak = []
    for name in sorted(blocks):
        body = "\n".join(blocks[name])
        hardened = (
            "no-new-privileges:true" in body
            and "cap_drop:" in body and "- ALL" in body
            and "privileged: true" not in body
            and "cap_add:" not in body
        )
        if not hardened:
            weak.append(name)
    results.append({
        "id": "services_unprivileged",
        "status": "pass" if not weak else "fail",
        "detail": "all services hardened" if not weak else ", ".join(weak),
    })
    bindings = [value for block in blocks.values() for value in _ports_in_block(block)]
    bad_bindings = [
        value for value in bindings
        if not (value.startswith("127.0.0.1:") or value.startswith("[::1]:"))
    ]
    results.append({
        "id": "published_ports_loopback",
        "status": "pass" if not bad_bindings else "fail",
        "detail": "loopback only" if not bad_bindings else ", ".join(bad_bindings),
    })
    return results


def _host_tooling_checks(root: Path) -> list[dict]:
    """Verify the scripts invoked by generated host units exist and parse."""
    import argparse
    import importlib.util

    def load_audited(name: str):
        path = root / "scripts" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"audited_{name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(name)
        module = importlib.util.module_from_spec(spec)
        old_path = list(sys.path)
        saved = {key: sys.modules.get(key) for key in ("backup_scheduler", "dr_common")}
        try:
            sys.path.insert(0, str(root / "scripts"))
            for key in saved:
                sys.modules.pop(key, None)
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = old_path
            for key, value in saved.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value
        return module

    required = (
        "scripts/backup_scheduler.py", "scripts/service_restart_recovery.py",
        "scripts/docker_volume_drill.py", "scripts/install_schedule.py",
    )
    missing = [name for name in required if not (root / name).is_file()]
    results = [{
        "id": "host_tooling_scripts_present",
        "status": "pass" if not missing else "fail",
        "detail": "all referenced scripts found" if not missing else ", ".join(missing),
    }]
    compile_errors = []
    for name in required:
        path = root / name
        if not path.is_file():
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            compile_errors.append(f"{name}:{exc.lineno}")
    results.append({
        "id": "host_tooling_syntax_ok",
        "status": "pass" if not compile_errors else "fail",
        "detail": "all scripts compile" if not compile_errors else ", ".join(compile_errors),
    })
    try:
        audited = load_audited("install_schedule")
        plan = audited.build_plan(argparse.Namespace(
            output_dir=str(root / "deploy" / "generated"), schedule="0 2 * * *",
            log_path=None, interval_hours=24, on_calendar="daily",
            environment_file="/etc/market-mind/market-mind.env",
        ))
        service = plan["files"][audited.BACKUP_SERVICE]
        cron = plan["files"][audited.CRON_FILE]
        valid = (
            "\nEnvironmentFile=" in service
            and ". /etc/market-mind/market-mind.env" in cron
            and "backup_scheduler.py run" in cron
        )
    except Exception:
        valid = False
    results.append({
        "id": "host_schedule_plan_valid",
        "status": "pass" if valid else "fail",
        "detail": "generated units and cron line validated" if valid else "plan validation failed",
    })
    return results


def build_report(root: Path) -> dict:
    root = Path(root)
    checks: list[dict] = []

    env = validate_dr_environment()
    checks.append({
        "id": "dr_environment",
        "status": "pass" if env["status"] == "ok" else "fail",
        "detail": f"{len(env['findings'])} finding(s); values not printed",
    })

    tls = _read(root, "deploy/tls/nginx-tls.conf.example")
    tls_tokens = ("TLSv1.2", "TLSv1.3", "Strict-Transport-Security",
                  "return 301 https://", "X-Forwarded-Proto https")
    missing_tls = [token for token in tls_tokens if token not in tls]
    checks.append({
        "id": "tls_template",
        "status": "pass" if not missing_tls else "fail",
        "detail": "template complete" if not missing_tls else "missing: " + ", ".join(missing_tls),
    })

    limits = _read(root, "frontend/nginx-limits.conf")
    server = _read(root, "frontend/nginx.conf")
    dockerfile = _read(root, "frontend/Dockerfile")
    ingress_tokens = (
        "limit_req_zone", "limit_conn_zone", "limit_req_status 429",
        "limit_conn_status 429", "map $http_x_forwarded_proto $mm_forwarded_proto",
    )
    missing_ingress = [token for token in ingress_tokens if token not in limits]
    if "limit_req zone=market_mind_api" not in server or "limit_conn market_mind_conn" not in server:
        missing_ingress.append("server applies perimeter limits")
    if "X-Forwarded-Proto $mm_forwarded_proto" not in server:
        missing_ingress.append("inner proxy preserves forwarded proto")
    if "X-Forwarded-Proto $scheme" in server:
        missing_ingress.append("inner proxy overwrites forwarded proto")
    if "00-ingress-limits.conf" not in dockerfile or "default.conf" not in dockerfile:
        missing_ingress.append("Dockerfile copy order")
    checks.append({
        "id": "ingress_limits_and_proto",
        "status": "pass" if not missing_ingress else "fail",
        "detail": "ingress complete" if not missing_ingress else "missing: " + ", ".join(missing_ingress),
    })

    checks.extend(_compose_checks(_read(root, "docker-compose.yml")))
    checks.extend(_host_tooling_checks(root))

    deploy = _read(root, "scripts/deploy_check.sh")
    deploy_tokens = ("command -v docker", "docker compose config --quiet", "/api/ready",
                     "backend_has_no_published_ports", "sqlite_integrity_ok")
    missing_deploy = [token for token in deploy_tokens if token not in deploy]
    checks.append({
        "id": "deploy_check_gates",
        "status": "pass" if not missing_deploy else "fail",
        "detail": "gates present" if not missing_deploy else "missing: " + ", ".join(missing_deploy),
    })

    failed = [check["id"] for check in checks if check["status"] != "pass"]
    return {
        "status": "pass" if not failed else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "checks": checks,
        "failed": failed,
        "scope": "static_offline_only",
        "external_verification": "not_claimed",
        "values_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    report = build_report(Path(args.root))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
