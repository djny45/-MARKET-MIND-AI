"""Safely prune old timestamped MARKET-MIND SQLite backups.

Dry-run is the default. Deletion requires --apply.
"""
import argparse
import json
import re
import sys
from pathlib import Path

BACKUP_NAME = re.compile(r"^market_mind-(\\d{8}T\\d{6}Z)\\.db$")


def plan_retention(directory: Path, keep: int = 14) -> dict:
    directory = directory.expanduser()
    if keep < 1:
        raise ValueError("keep_must_be_at_least_one")
    if directory.is_symlink():
        raise ValueError("backup_directory_must_not_be_symlink")
    if not directory.exists() or not directory.is_dir():
        raise NotADirectoryError("backup_directory_not_found")
    candidates = []
    for path in directory.iterdir():
        if not BACKUP_NAME.fullmatch(path.name):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("matching_backup_must_be_regular_file:" + path.name)
        candidates.append(path)
    candidates.sort(key=lambda item: item.name, reverse=True)
    retained = candidates[:keep]
    expired = candidates[keep:]
    return {
        "directory": str(directory.resolve()),
        "keep": keep,
        "discovered": len(candidates),
        "retained": [item.name for item in retained],
        "expired": [item.name for item in expired],
    }


def prune_backups(directory: Path, keep: int = 14, apply: bool = False) -> dict:
    plan = plan_retention(directory, keep)
    deleted = []
    if apply:
        root = Path(plan["directory"])
        for name in plan["expired"]:
            target = root / name
            if target.is_symlink() or not target.is_file():
                raise ValueError("backup_changed_before_delete:" + name)
            target.unlink()
            deleted.append(name)
    return {**plan, "mode": "apply" if apply else "dry-run", "deleted": deleted}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prune timestamped MARKET-MIND SQLite backups.")
    parser.add_argument("directory", nargs="?", default="./backups")
    parser.add_argument("--keep", type=int, default=14, help="Number of newest backups to retain (default: 14)")
    parser.add_argument("--apply", action="store_true", help="Actually delete expired backups; default is dry-run")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prune_backups(Path(args.directory), args.keep, args.apply), indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
