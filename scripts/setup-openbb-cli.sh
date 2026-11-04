#!/usr/bin/env bash
set -euo pipefail

# Install OpenBB CLI into a dedicated virtual environment without modifying
# MARKET-MIND-AI's backend environment.
# Upstream OpenBB CLI v2 requires Python >=3.11,<4.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

VENV=".venv-openbb"
PYTHON_BIN="${PYTHON_BIN:-python3}"
created_venv=0
setup_complete=0

cleanup_on_failure() {
  status=$?
  if [[ "$created_venv" -eq 1 && "$setup_complete" -eq 0 ]]; then
    echo "Setup failed; removing incomplete environment: $VENV" >&2
    rm -rf -- "$VENV"
  fi
  exit "$status"
}
trap cleanup_on_failure EXIT

if [[ -e "$VENV" ]]; then
  echo "Refusing to reuse existing environment: $VENV" >&2
  echo "Activate it manually or remove it after reviewing its contents." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN to a Python 3.11+ executable." >&2
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "OpenBB CLI v2 requires Python 3.11+")'
"$PYTHON_BIN" -m venv "$VENV"
created_venv=1

if [[ -f "$VENV/bin/python" ]]; then
  VENV_PYTHON="$VENV/bin/python"
  OPENBB="$VENV/bin/openbb"
elif [[ -f "$VENV/Scripts/python.exe" ]]; then
  VENV_PYTHON="$VENV/Scripts/python.exe"
  OPENBB="$VENV/Scripts/openbb.exe"
else
  echo "Could not locate Python inside $VENV." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install openbb-cli
"$VENV_PYTHON" -m pip show openbb-cli

if [[ ! -x "$OPENBB" ]]; then
  echo "OpenBB executable not found after installation: $OPENBB" >&2
  exit 1
fi
"$OPENBB" --help

setup_complete=1
echo
echo "OpenBB CLI installed in $VENV."
echo "Activate the environment before using it:"
echo "  Linux/macOS: source $VENV/bin/activate"
echo "  PowerShell:  .\\$VENV\\Scripts\\Activate.ps1"
echo
echo "For the MARKET-MIND-AI API adapter, set OPENBB_CLI_ENABLED=true only"
echo "in trusted local development. Do not expose it on a public deployment."
