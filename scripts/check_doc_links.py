#!/usr/bin/env python3
"""Check that relative links in README and docs resolve to real files.

A landing page is only useful if its links work. This runs locally and in tests
so documentation rot is caught by CI instead of by a visitor.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LINK_PATTERN = re.compile(r"\]\(([^)\s]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "tel:")
# Vendored upstream reference material keeps its own (often relative) links;
# it is not our documentation and must not be rewritten.
SKIP_DIRECTORIES = (REPO_ROOT / "docs" / "upstream-intelligence",)


def markdown_files() -> list[Path]:
    files = [REPO_ROOT / "README.md"]
    files.extend(sorted((REPO_ROOT / "docs").rglob("*.md")))
    return [
        path for path in files
        if path.is_file() and not any(
            parent == path or parent in path.parents for parent in SKIP_DIRECTORIES
        )
    ]


def broken_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    broken = []
    for raw in LINK_PATTERN.findall(text):
        target = raw.strip()
        if target.startswith(SKIP_PREFIXES):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            broken.append(f"{path.relative_to(REPO_ROOT)} -> {raw}")
    return broken


def main() -> int:
    problems: list[str] = []
    for path in markdown_files():
        problems.extend(broken_links(path))
    if problems:
        print(f"{len(problems)} broken relative link(s):")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"all relative links resolve ({len(markdown_files())} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
