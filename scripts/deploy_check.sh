#!/usr/bin/env bash
# Verify an already-running MARKET-MIND-AI Compose deployment.
# This script never prints environment values or container logs.
set -Eeuo pipefail

WITH_N8N=0
START=0
BACKUP_DRILL=0
for arg in "$@"; do
  case "$arg" in
    --with-n8n) WITH_N8N=1 ;;
    --start) START=1 ;;
    --backup-drill) BACKUP_DRILL=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/deploy_check.sh [--start] [--with-n8n] [--backup-drill]
  --start     Build/start the Compose stack before checking it.
  --with-n8n  Also require the optional n8n profile to be running and healthy.
  --backup-drill  Create a host-persisted SQLite backup and verify disposable restore.
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

PASS=0
FAIL=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf 'FAIL  %s\n' "$label"
    FAIL=$((FAIL + 1))
  fi
}
wait_http() {
  local url="$1" attempts="${2:-30}"
  for ((i=1; i<=attempts; i++)); do
    if curl --fail --silent --show-error --max-time 3 "$url" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}
container_id() {
  docker compose ps -q "$1"
}
is_loopback_binding() {
  local service="$1" container
  container="$(container_id "$service")"
  [[ -n "$container" ]] || return 1
  python3 - "$container" "$service" <<'PY'
import json, subprocess, sys
container, service = sys.argv[1:]
raw = subprocess.check_output(
    ["docker", "inspect", container, "--format", "{{json .HostConfig.PortBindings}}"],
    text=True,
)
bindings = json.loads(raw or "{}")
expected = {"frontend": ("8080/tcp", "8080"), "n8n": ("5678/tcp", "5678")}
port, host_port = expected[service]
items = bindings.get(port) or []
if not items or any(item.get("HostIp") != "127.0.0.1" or item.get("HostPort") != host_port for item in items):
    raise SystemExit(1)
PY
}
backend_has_no_published_ports() {
  local container
  container="$(container_id backend)"
  [[ -n "$container" ]] || return 1
  python3 - "$container" <<'PY'
import json, subprocess, sys
raw = subprocess.check_output(
    ["docker", "inspect", sys.argv[1], "--format", "{{json .HostConfig.PortBindings}}"],
    text=True,
)
bindings = json.loads(raw or "{}")
if any(bindings.values()):
    raise SystemExit(1)
PY
}

agent_supervisor_running() {
  local container
  container="$(container_id agent-supervisor)"
  [[ -n "$container" ]] || return 1
  [[ "$(docker inspect "$container" --format '{{.State.Running}}')" == "true" ]]
}
sqlite_integrity_ok() {
  docker compose exec -T backend python -c "import sqlite3; c=sqlite3.connect('/data/market_mind.db'); result=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close(); raise SystemExit(0 if result == 'ok' else 1)"
}

echo "MARKET-MIND-AI deployment verification"
command -v docker >/dev/null 2>&1 || { echo "FAIL  Docker CLI missing"; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "FAIL  curl missing"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "FAIL  Python 3 missing"; exit 2; }
check "Docker Compose plugin available" docker compose version
check "Compose configuration valid" docker compose config --quiet
if (( START )); then
  if (( WITH_N8N )); then
    check "Start core stack and n8n profile" docker compose --profile n8n up --build -d
  else
    check "Start core stack" docker compose up --build -d
  fi
fi

check "Backend readiness endpoint" wait_http "http://127.0.0.1:8080/api/ready" 30
check "Frontend responds" wait_http "http://127.0.0.1:8080/" 10
check "Backend has no host-published ports" backend_has_no_published_ports
check "Frontend binds only to loopback" is_loopback_binding frontend
check "Agent supervisor process is running" agent_supervisor_running
check "Persistent SQLite database integrity" sqlite_integrity_ok
if (( BACKUP_DRILL )); then
  check "Host backup and disposable restore drill" bash scripts/backup_restore_drill.sh
fi

if (( WITH_N8N )); then
  check "n8n health endpoint" wait_http "http://127.0.0.1:5678/healthz" 45
  check "n8n binds only to loopback" is_loopback_binding n8n
  check "Backend reaches n8n over Compose network" docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://n8n:5678/healthz', timeout=5)"
fi

echo "Result: $PASS passed, $FAIL failed"
if (( FAIL )); then
  echo "Review container status with: docker compose ps"
  echo "Inspect service logs locally; do not share logs containing secrets."
  exit 1
fi
echo "Deployment checks passed. This does not verify reviewer credentials or a workflow import."
