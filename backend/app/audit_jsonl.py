"""Size-capped append-only JSONL audit logs.

Several research subsystems append one JSON object per event to a ``.jsonl``
file. Left alone those files grow without bound: on a long-running research host
they are the one artefact with no retention policy at all, and a full disk stops
research, backups and the API together.

Rotation keeps the evidence: the active file is renamed to ``<name>.1`` and older
archives shift up to ``<name>.N``, so nothing is dropped silently. Caps are
configurable per deployment:

* ``MARKET_MIND_AUDIT_LOG_MAX_BYTES`` — rotate once the active file would exceed
  this size (default 5 MiB).
* ``MARKET_MIND_AUDIT_LOG_KEEP`` — rotated archives to retain (default 3).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_KEEP = 3


def _positive_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def limits() -> tuple[int, int]:
    """Return ``(max_bytes, keep)`` from the environment, with safe defaults."""
    return (
        _positive_int_env("MARKET_MIND_AUDIT_LOG_MAX_BYTES", DEFAULT_MAX_BYTES, minimum=1024),
        _positive_int_env("MARKET_MIND_AUDIT_LOG_KEEP", DEFAULT_KEEP),
    )


def rotate(path: Path, *, keep: int) -> list[str]:
    """Shift ``path`` into ``path.1``..``path.{keep}``; return archived names."""
    path = Path(path)
    if keep < 1 or not path.exists():
        return []
    archived: list[str] = []
    try:
        Path(f"{path}.{keep}").unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return []
    for index in range(keep - 1, 0, -1):
        source = Path(f"{path}.{index}")
        if not source.exists():
            continue
        try:
            os.replace(source, Path(f"{path}.{index + 1}"))
            archived.append(source.name)
        except OSError:
            return archived
    try:
        os.replace(path, Path(f"{path}.1"))
        archived.append(path.name)
    except OSError:
        return archived
    return archived


def append_record(
    path: str | os.PathLike[str],
    record: dict[str, Any],
    *,
    max_bytes: int | None = None,
    keep: int | None = None,
) -> dict:
    """Append ``record`` as one JSON line, rotating first if the cap is hit."""
    target = Path(path)
    configured_max, configured_keep = limits()
    cap = configured_max if max_bytes is None else int(max_bytes)
    archives = configured_keep if keep is None else int(keep)
    line = json.dumps(record, sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    rotated: list[str] = []
    try:
        current = target.stat().st_size
    except FileNotFoundError:
        current = 0
    if current and current + len(encoded) > cap:
        rotated = rotate(target, keep=archives)
        current = 0
    separator = b""
    if current:
        # A crash mid-write can leave an unterminated final line. Start a new
        # line so the truncated record stays isolated (readers skip it) instead
        # of being glued to the next event, which would corrupt both.
        try:
            with open(target, "rb") as existing:
                existing.seek(-1, os.SEEK_END)
                if existing.read(1) != b"\n":
                    separator = b"\n"
        except OSError:
            separator = b""
    with open(target, "ab") as handle:
        if separator:
            handle.write(separator)
        handle.write(encoded)
    return {"path": str(target), "bytes": len(encoded), "rotated": rotated}


def _ordered_files(path: Path) -> list[Path]:
    """Oldest first: ``name.3``, ``name.2``, ``name.1``, then the active file."""
    archives = []
    for candidate in path.parent.glob(f"{path.name}.*"):
        suffix = candidate.name.rsplit(".", 1)[-1]
        if suffix.isdigit() and candidate.is_file():
            archives.append((int(suffix), candidate))
    ordered = [candidate for _index, candidate in sorted(archives, key=lambda item: -item[0])]
    ordered.append(path)
    return ordered


def read_records(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Read every record, including rotated archives, oldest first.

    A line truncated by a crash mid-write is skipped instead of raising: a
    half-written last line must not take down the endpoint that reports on it.
    """
    records: list[dict[str, Any]] = []
    for candidate in _ordered_files(Path(path)):
        try:
            handle = open(candidate, encoding="utf-8")
        except (FileNotFoundError, OSError):
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    return records


def log_stats(path: str | os.PathLike[str]) -> dict:
    """Report sizes for health/ops output without reading log contents."""
    target = Path(path)
    archives = sorted(
        (candidate for candidate in target.parent.glob(f"{target.name}.*")
         if candidate.is_file()),
        key=lambda candidate: candidate.name,
    )
    try:
        active = target.stat().st_size
    except FileNotFoundError:
        active = 0
    return {
        "path": str(target),
        "active_bytes": active,
        "archives": [{"name": item.name, "bytes": item.stat().st_size} for item in archives],
        "total_bytes": active + sum(item.stat().st_size for item in archives),
    }
