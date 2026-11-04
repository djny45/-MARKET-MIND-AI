#!/usr/bin/env bash
set -euo pipefail

# Install OpenBB CLI into a dedicated virtual environment without modifying
# MARKET-MIND-AI's backend environment.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

VENV=".venv-openbb"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -e "$VENV" ]]; then
  echo "Refusing to reuse existing environment: $VENV" >&2
  echo "Activate it manually or remove it after reviewing its contents." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN to your Python 3.10+ executable." >&2
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else "OpenBB CLI setup requires Python 3.10+")'

"$PYTHON_BIN" -m venv "$VENV"

if [[ -f "$VENV/bin/python" ]]; then
  VENV_PYTHON="$VENV/bin/python"
elif [[ -f "$VENV/Scripts/python.exe" ]]; then
  VENV_PYTHON="$VENV/Scripts/python.exe"
else
  echo "Could not locate Python inside $VENV." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install openbb-cli
"$VENV_PYTHON" -m pip show openbb-cli
"$VENV_PYTHON" -m openbb --help

echo
echo "OpenBB CLI installed in $VENV."
echo "Activate the environment before using it:"
echo "  Linux/macOS: source $VENV/bin/activate"
echo "  PowerShell:  .\\$VENV\\Scripts\\Activate.ps1"
echo
echo "For the MARKET-MIND-AI API adapter, set OPENBB_CLI_ENABLED=true only"
echo "in trusted local development. Do not expose it on a public deployment."
