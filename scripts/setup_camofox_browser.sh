#!/usr/bin/env bash
# Install and start a local, research-only Camofox Browser REST server.
# The MCP adapter registered in .mcp.json / .cursor / .codex forwards to it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKOUT="$ROOT/third_party/camofox-browser"
RUNTIME="$CHECKOUT/.runtime"

# Prefer a local Node 24 when the system Node is older. Camofox's own docs say
# Node >= 22, but its openclaw dependency currently requires >= 24.16.
LOCAL_NODE_BIN=""
for candidate in "$HOME/.local/node24/bin" "$HOME/.local/node22/bin"; do
  if [ -x "$candidate/node" ]; then
    LOCAL_NODE_BIN="$candidate"
    break
  fi
done
if [ -n "$LOCAL_NODE_BIN" ]; then
  export PATH="$LOCAL_NODE_BIN:$PATH"
  echo "Using local Node: $(node -v) ($LOCAL_NODE_BIN)"
fi

# Camoufox needs GTK3 at runtime. When system libraries are unavailable (this
# container has no root), unpack the required Ubuntu .debs into ~/.local/gtk3
# and expose that directory to the browser process.
GTK_LIB_DIR="$HOME/.local/gtk3/usr/lib/x86_64-linux-gnu"
if [ -d "$GTK_LIB_DIR" ]; then
  export LD_LIBRARY_PATH="$GTK_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  echo "Exposing local GTK3 libs: $GTK_LIB_DIR"
fi

if [ ! -d "$CHECKOUT/mcp" ]; then
  echo "Cloning Camofox Browser into $CHECKOUT ..."
  mkdir -p "$(dirname "$CHECKOUT")"
  git clone --depth 1 https://github.com/jo-inc/camofox-browser.git "$CHECKOUT"
fi

NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
if [ "$NODE_MAJOR" -lt 24 ]; then
  echo "ERROR: Camofox's openclaw dependency requires Node.js >= 24.16 (found $(node -v))." >&2
  echo "Install a local Node 24 under ~/.local/node24/bin and retry." >&2
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
