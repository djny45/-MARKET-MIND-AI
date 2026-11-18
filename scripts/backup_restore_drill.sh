#!/usr/bin/env bash
# Create a host-persisted SQLite backup and verify restore into a disposable DB.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${1:-$ROOT/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_NAME="market_mind-${STAMP}.db"
CONTAINER_BACKUP="/tmp/${BACKUP_NAME}"
CONTAINER_RESTORE="/tmp/restore-drill-${STAMP}.db"
mkdir -p "$BACKUP_DIR"
DEST="$BACKUP_DIR/$BACKUP_NAME"
[[ ! -e "$DEST" ]] || { echo "Refusing to overwrite $DEST" >&2; exit 2; }
cleanup() {
  docker compose exec -T backend sh -c "rm -f '$CONTAINER_BACKUP' '$CONTAINER_RESTORE'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Creating online SQLite backup from the running backend volume…"
docker compose exec -T backend python backup_database.py "$CONTAINER_BACKUP" --source /data/market_mind.db
echo "Restoring backup to a disposable database inside the backend container…"
docker compose exec -T backend python restore_database.py "$CONTAINER_BACKUP" "$CONTAINER_RESTORE"
echo "Copying verified backup to host: $DEST"
docker compose cp "backend:$CONTAINER_BACKUP" "$DEST"
python3 - "$DEST" <<'PY'
import hashlib, sqlite3, sys
path = sys.argv[1]
with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if result != "ok" or "market_bars" not in tables:
    raise SystemExit("Host backup failed integrity/schema verification")
with open(path, "rb") as handle:
    digest = hashlib.sha256(handle.read()).hexdigest()
print(f"PASS  host backup integrity_check=ok sha256={digest}")
PY
echo "Backup/restore drill passed. Store this file encrypted and off-host before relying on it."
