#!/usr/bin/env bash
set -euo pipefail

# Import the upstream OpenBB source tree into MARKET-MIND-AI.
# This is intentionally an explicit, local operation: the OpenBB repository is
# large and the GitHub Contents API cannot perform a repository-wide import.
# Requires git and git-subtree. Run from the MARKET-MIND-AI repository root.

UPSTREAM_URL="https://github.com/openbq-org/OpenBB.git"
UPSTREAM_REF="develop"
DEST="vendor/openbb"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Run this script from inside a Git repository." >&2
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ -e "$DEST" ]]; then
  echo "Refusing to overwrite existing path: $DEST" >&2
  exit 1
fi

if ! git subtree --version >/dev/null 2>&1; then
  echo "git-subtree is required. Install it, then retry." >&2
  exit 1
fi

echo "Importing upstream OpenBB ($UPSTREAM_REF) into $DEST."
echo "This may take substantial time and disk space."
git subtree add --prefix="$DEST" "$UPSTREAM_URL" "$UPSTREAM_REF" --squash

echo
echo "OpenBB source imported. Review vendor/openbb/LICENSE and upstream notices."
echo "Next: install OpenBB in a dedicated Python environment and configure the CLI bridge."
