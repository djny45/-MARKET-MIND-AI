#!/usr/bin/env bash
set -euo pipefail

# Verify the OpenBB Git subtree after scripts/import-openbb.sh completes.
# Run from the MARKET-MIND-AI repository root.

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Run this verifier inside a Git repository." >&2
  exit 1
}
cd "$ROOT"

DEST="vendor/openbb"
if [[ ! -d "$DEST" ]]; then
  echo "OpenBB source directory is missing: $DEST" >&2
  echo "Run: bash scripts/import-openbb.sh" >&2
  exit 1
fi

for required in LICENSE README.md openbb_platform cli; do
  if [[ ! -e "$DEST/$required" ]]; then
    echo "OpenBB import looks incomplete: missing $DEST/$required" >&2
    exit 1
  fi
done

if ! git ls-tree -d HEAD "$DEST" >/dev/null 2>&1; then
  echo "$DEST is not tracked in the current commit." >&2
  echo "Commit the completed subtree import before verifying." >&2
  exit 1
fi

echo "OpenBB source import verified:"
echo "  Path: $DEST"
echo "  Upstream: https://github.com/openbq-org/OpenBB"
echo "  Required source markers: present"
echo "  Git tracking: present"
echo
echo "This verifies source presence only; it does not install dependencies or"
echo "validate provider credentials, data access, or interactive CLI behavior."
