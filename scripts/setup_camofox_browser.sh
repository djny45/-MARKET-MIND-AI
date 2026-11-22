#!/usr/bin/env bash
# Install and start a local, research-only Camofox Browser REST server.
# The MCP adapter registered in .mcp.json / .cursor / .codex forwards to it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKOUT="$ROOT/third_party/camofox-browser"
RUNTIME="$CHECKOUT/.runtime"

# Prefer a locally installed Node 22 (e.g. ~/.local/node22) when the system
# Node is older than Camofox's minimum. Keeps the toolchain project-local.
LOCAL_NODE_BIN="$HOME/.local/node22/bin"
if [ -x "$LOCAL_NODE_BIN/node" ]; then
  export PATH="$LOCAL_NODE_BIN:$PATH"
  echo "Using local Node: $(node -v) ($LOCAL_NODE_BIN)"
fi

if [ ! -d "$CHECKOUT/mcp" ]; then
  echo "Cloning Camofox Browser into $CHECKOUT ..."
  mkdir -p "$(dirname "$CHECKOUT")"
  git clone --depth 1 https://github.com/jo-inc/camofox-browser.git "$CHECKOUT"
fi

NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
if [ "$NODE_MAJOR" -lt 22 ]; then
  echo "ERROR: Camofox requires Node.js >= 22 (found $(node -v))." >&2
  exit 1
fi

mkdir -p "$RUNTIME/profile" "$RUNTIME/cookies" "$RUNTIME/uploads"
cd "$CHECKOUT"
echo "Installing dependencies (downloads Camoufox on first run, ~300 MB) ..."
npm install

echo "Starting REST server on 127.0.0.1:9377 ..."
unset CAMOFOX_API_KEY CAMOFOX_ACCESS_KEY CAMOFOX_ADMIN_KEY
CAMOFOX_BIND_HOST=127.0.0.1 \
CAMOFOX_PORT=9377 \
CAMOFOX_PROFILE_DIR="$RUNTIME/profile" \
CAMOFOX_COOKIES_DIR="$RUNTIME/cookies" \
CAMOFOX_UPLOADS_DIR="$RUNTIME/uploads" \
  nohup npm start >"$RUNTIME/server.log" 2>&1 &
echo $! >"$RUNTIME/server.pid"

echo "Started. Health check: curl http://127.0.0.1:9377/health"
echo "Log: $RUNTIME/server.log"
echo
echo "Safety: research only. No API/access keys configured, so cookie import is disabled."
echo "Do not use this browser for brokerage orders, payments, credentials, or personal data."
