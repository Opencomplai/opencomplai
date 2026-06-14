#!/usr/bin/env bash
set -euo pipefail

echo "Opencomplai bootstrap"
echo "====================="

# --- Python checks ---
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_PYTHON="3.11"
if [[ "$(printf '%s\n' "$REQUIRED_PYTHON" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_PYTHON" ]]; then
    echo "ERROR: Python $REQUIRED_PYTHON+ required. Found: $PYTHON_VERSION"
    exit 1
fi
echo "Python $PYTHON_VERSION — OK"

# --- uv ---
if ! command -v uv &>/dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.cargo/env" 2>/dev/null || true
fi
echo "uv $(uv --version) — OK"

# --- Node.js checks ---
NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' || echo "0")
REQUIRED_NODE="20"
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [[ "$NODE_MAJOR" -lt "$REQUIRED_NODE" ]]; then
    echo "ERROR: Node.js $REQUIRED_NODE+ required. Found: $NODE_VERSION"
    echo "Install via: https://nodejs.org or nvm"
    exit 1
fi
echo "Node.js v$NODE_VERSION — OK"

# --- pnpm ---
if ! command -v pnpm &>/dev/null; then
    echo "pnpm not found. Installing via corepack..."
    corepack enable
    corepack prepare pnpm@latest --activate
fi
echo "pnpm $(pnpm --version) — OK"

# --- Docker ---
if ! command -v docker &>/dev/null; then
    echo "WARNING: Docker not found. Phases 7+ require Docker. See https://docs.docker.com/get-docker/"
else
    echo "Docker $(docker --version | awk '{print $3}' | tr -d ',') — OK"
fi

# --- Install Python workspace dependencies ---
echo ""
echo "Installing Python workspace dependencies..."
uv sync --all-packages

# --- Install Node.js dependencies ---
echo "Installing Node.js dependencies..."
pnpm install --frozen-lockfile

# --- Pre-commit hooks ---
if command -v pre-commit &>/dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
else
    echo "pre-commit not found — skipping (run: pip install pre-commit)"
fi

# --- Doctor check ---
echo ""
echo "Running environment check..."
python3 scripts/doctor.py

echo ""
echo "Bootstrap complete."
echo "Run 'pytest packages/' to verify the Python stack."
echo "Run 'cd services/gateway-api && pnpm test' to verify the Node.js stack."
