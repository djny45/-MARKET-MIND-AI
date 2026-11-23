"""Shared helpers for MARKET-MIND backup and disaster-recovery automation.

Research-only platform: these helpers move SQLite research data and emit
operator-configured alerts. They contain no trading, wallet, signing or
order-routing capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPO_ROOT / "backend" / "backup_database.py"
RESTORE_SCRIPT = REPO_ROOT / "backend" / "restore_database.py"

BACKUP_PREFIX = "market_mind-"
LOCK_SUFFIX = ".lock"

# Only these keys are ever sent to an incident webhook. This whitelist keeps
# credentials, tokens and operator notes out of alert payloads.
_ALERT_KEYS = frozenset({
    "event", "error_type", "phase", "backup", "destination", "reason",
    "bytes", "sha256", "status", "elapsed_seconds", "retained", "pruned",
})


class DrError(RuntimeError):
    """Base class for recoverable DR automation errors."""


class DrLocked(DrError):
    """Another backup/restore process holds the state-directory lock."""


class DrInterrupted(DrError):
    """A previous run left an incomplete journal that must be resumed."""


def utcstamp() -> str:
    """UTC timestamp suitable for a filename (no colons or spaces)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def positive_int(value, name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool):
        raise DrError(f"{name}_must_be_an_integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DrError(f"{name}_must_be_an_integer") from exc
    if parsed < minimum:
        raise DrError(f"{name}_must_be_at_least_{minimum}")
    return parsed


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    return positive_int(os.getenv(name, str(default)), name, minimum=minimum)


def parse_bool(value, name: str = "value") -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    raise DrError(f"{name}_must_be_a_boolean")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def atomic_write_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def write_checksum(path: Path, digest: str) -> Path:
    """Write a portable sha256sum-compatible sidecar next to a backup."""
    path = Path(path)
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return sidecar


def read_checksum(sidecar: Path) -> str | None:
    """Return the digest recorded in a sha256sum sidecar, if well formed."""
    try:
        first = Path(sidecar).read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None
    parts = first.split()
    if len(parts) != 2 or len(parts[0]) != 64:
        return None
    return parts[0].lower()


def verify_checksum(backup: Path, sidecar: Path | None = None) -> dict:
    backup = Path(backup)
    sidecar = sidecar or backup.with_name(backup.name + ".sha256")
    recorded = read_checksum(sidecar)
    if recorded is None:
        return {"status": "missing_sidecar", "backup": str(backup)}
    if not backup.is_file():
        return {"status": "backup_not_found", "backup": str(backup)}
    actual = sha256_file(backup)
    if actual != recorded:
        return {
            "status": "checksum_mismatch", "backup": str(backup),
            "recorded": recorded, "actual": actual,
        }
    return {"status": "verified", "backup": str(backup), "sha256": actual}


def readonly_uri(path: Path) -> str:
    """Build a correctly escaped SQLite read-only URI (handles '?', '#', spaces)."""
    return Path(path).resolve().as_uri() + "?mode=ro"


def database_fingerprint(path: Path) -> dict:
    """Collect integrity, per-table row counts and migration version for a DB."""
    database = Path(path)
    result = {
        "integrity": "unavailable",
        "table_counts": {},
        "schema_version": None,
        "bytes": database.stat().st_size if database.is_file() else 0,
    }
    try:
        with sqlite3.connect(readonly_uri(database), uri=True) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            result["integrity"] = row[0] if row else "no_integrity_result"
            names = [
                name for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            for name in names:
                result["table_counts"][name] = connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
            if "schema_migrations" in names:
                result["schema_version"] = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()[0]
    except sqlite3.Error as exc:
        result["integrity"] = type(exc).__name__
    return result


def run_repo_script(script: Path, args: list[str], *, timeout: int = 180,
                    env: dict | None = None) -> dict:
    """Run one of the repository's own backup/restore scripts and parse its JSON."""
    command = [sys.executable, str(Path(script))] + [str(item) for item in args]
    try:
        completed = subprocess.run(
            command, cwd=str(REPO_ROOT), env=env or os.environ.copy(),
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None, "error_type": "TimeoutExpired",
            "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or ""),
            "payload": None,
        }
    payload = None
    text = completed.stdout.strip()
    try:
        payload = json.loads(text)
    except ValueError:
        # Repository scripts emit indented JSON; extract the outermost object.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                payload = json.loads(text[start:end + 1])
            except ValueError:
                pass
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload": payload,
    }


def parse_upload_command(command: str) -> list[str]:
    """Tokenize an operator-provided upload hook without invoking a shell.

    Supported placeholders in each token: {backup}, {sha256}, {name},
    {destination}. Secrets must be supplied by the operator's environment,
    never embedded in this command string.
    """
    if not command or not command.strip():
        raise DrError("upload_command_is_empty")
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise DrError("upload_command_invalid_shell_syntax") from exc
    if not tokens:
        raise DrError("upload_command_is_empty")
    return tokens


def run_upload_command(command: str, *, backup: Path, sha256: str,
                       timeout: int = 300, env: dict | None = None) -> dict:
    tokens = [
        token.replace("{backup}", str(backup))
        .replace("{sha256}", sha256)
        .replace("{name}", backup.name)
        .replace("{destination}", str(backup.parent))
        for token in parse_upload_command(command)
    ]
    try:
        completed = subprocess.run(
            tokens, cwd=str(REPO_ROOT), env=env or os.environ.copy(),
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "error_type": type(exc).__name__}
    return {
        "status": "uploaded" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "error_type": "UploadCommandFailed" if completed.returncode else None,
        "stdout": completed.stdout.strip()[-2000:],
        "stderr": completed.stderr.strip()[-2000:],
    }


def _sanitize_alert_detail(detail: dict | None) -> dict:
    clean: dict = {}
    for key, value in (detail or {}).items():
        if key not in _ALERT_KEYS or value is None:
            continue
        if isinstance(value, bool):
            clean[key] = value
        elif isinstance(value, int):
            clean[key] = value
        else:
            clean[key] = str(value)[:512]
    return clean


def send_alert(event: str, status: str, detail: dict | None = None,
               *, timeout: float = 5.0) -> dict:
    """Best-effort incident webhook hook. Never logs or emits the webhook URL.

    Configure with MARKET_MIND_INCIDENT_WEBHOOK_URL (http/https only). With no
    URL configured this is a no-op, so local drills remain offline.
    """
    url = os.getenv("MARKET_MIND_INCIDENT_WEBHOOK_URL", "").strip()
    if not url:
        return {"status": "disabled", "event": event}
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"status": "invalid_webhook_url", "event": event}
    payload = {
        "source": "market-mind-dr",
        "mode": "research-only",
        "event": event,
        "status": status,
        "timestamp": iso_now(),
        "detail": _sanitize_alert_detail(detail),
    }
    request = Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1024)
    except (URLError, OSError, ValueError) as exc:
        return {"status": "delivery_failed", "event": event,
                "error_type": type(exc).__name__}
    return {"status": "sent", "event": event}


class DrLock:
    """Inter-process lock for DR state directories with stale-PID recovery.

    A PID alone is not a safe identity: after a crash or host reboot the PID can
    be recycled by an unrelated process, which would make the lock look held
    forever and silently stop every scheduled backup. A lock is therefore stale
    when its PID is dead, when the live PID is not the process that wrote the
    lock (start time mismatch), or when the lock is older than its ceiling.
    """

    # Ceiling for a lock a live process claims to hold. A backup that needs
    # longer than this is stuck, not busy.
    DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60

    def __init__(self, state_dir: Path, name: str = "backup",
                 max_age_seconds: int | None = None):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / f"{name}{LOCK_SUFFIX}"
        if max_age_seconds is None:
            max_age_seconds = env_int("MARKET_MIND_DR_LOCK_MAX_AGE",
                                      self.DEFAULT_MAX_AGE_SECONDS, minimum=60)
        self.max_age_seconds = max_age_seconds

    def _read_pid(self, path: Path | None = None) -> int | None:
        """Read the PID from a specific lock file (defaults to this lock)."""
        payload = read_json(self.path if path is None else path)
        if not payload:
            return None
        pid = payload.get("pid")
        return pid if isinstance(pid, int) and not isinstance(pid, bool) else None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _pid_start(pid: int) -> str | None:
        """Process start time in clock ticks: a stable identity for a PID.

        A PID can be recycled, but a (pid, starttime) pair cannot be reused while
        the original process lives, so comparing it detects a recycled PID.
        Returns None when it cannot be read (non-Linux, permissions).
        """
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            return None
        # Fields after the (possibly space-containing) comm field: state is field
        # 3, so starttime is the 20th field after the closing parenthesis.
        tail = stat.rsplit(")", 1)
        if len(tail) != 2:
            return None
        fields = tail[1].split()
        return fields[19] if len(fields) > 19 else None

    def _age_exceeded(self, payload: dict) -> bool:
        created = str(payload.get("created_at") or "").strip()
        if not created:
            return False
        try:
            stamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            return False
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - stamp).total_seconds() > self.max_age_seconds

    def _is_stale(self, path: Path) -> tuple[bool, int | None, str]:
        payload = read_json(path) or {}
        pid = payload.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool):
            return True, None, "lock_missing_pid"
        if not self._pid_alive(pid):
            return True, pid, "pid_not_running"
        recorded_start = payload.get("pid_start")
        current_start = self._pid_start(pid)
        if recorded_start is not None and current_start is not None:
            if str(recorded_start) != str(current_start):
                return True, pid, "pid_reused_by_other_process"
        # Identity confirmed or unverifiable: the age ceiling is the backstop.
        if self._age_exceeded(payload):
            return True, pid, "lock_age_exceeded"
        return False, pid, "held"

    def acquire(self) -> dict:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            stale, pid, reason = self._is_stale(self.path)
            if not stale:
                raise DrLocked(f"dr_lock_held_by_pid_{pid}")
            self.path.unlink()
            return {"status": "acquired_after_stale_lock_recovery",
                    "stale_pid": pid, "stale_reason": reason}
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise DrLocked("dr_lock_race") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "pid": os.getpid(),
                "pid_start": self._pid_start(os.getpid()),
                "host": socket.gethostname(),
                "created_at": iso_now(),
            }, sort_keys=True) + "\n")
        return {"status": "acquired"}

    def release(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def stale_count(self) -> int:
        """Remove dead, recycled or expired locks; never a live DR process."""
        if not self.state_dir.is_dir():
            return 0
        stale = 0
        for path in self.state_dir.glob(f"*{LOCK_SUFFIX}"):
            is_stale, _pid, _reason = self._is_stale(path)
            if is_stale:
                path.unlink()
                stale += 1
        return stale

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False
