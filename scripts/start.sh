#!/usr/bin/env bash
# Starts the SG Expenditure Tracker: backend (FastAPI) + frontend (Vite) dev
# servers in the background, waits for both to come up, opens the app in
# your browser, and stops both when you Ctrl+C this script.
#
# Run with: ./scripts/start.sh  (or: bash scripts/start.sh)

set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # this script lives in scripts/, repo root is one level up
backend_dir="$root/backend"
frontend_dir="$root/frontend"
log_dir="$(mktemp -d)"
backend_log="$log_dir/backend.log"
frontend_log="$log_dir/frontend.log"
: >"$backend_log"
: >"$frontend_log"

backend_pid=""
frontend_pid=""
tail_pid=""

cleanup() {
    [ -n "$tail_pid" ] && kill "$tail_pid" 2>/dev/null
    [ -n "$backend_pid" ] && kill "$backend_pid" 2>/dev/null
    [ -n "$frontend_pid" ] && kill "$frontend_pid" 2>/dev/null
}
trap cleanup EXIT INT TERM

port_up() {
    # Vite binds to localhost/::1, uvicorn binds to 127.0.0.1 - try both
    # rather than assuming, so "already running" detection actually works.
    local port="$1" path="${2:-/}"
    curl -sf -o /dev/null --max-time 1 "http://127.0.0.1:${port}${path}" 2>/dev/null && return 0
    curl -sf -o /dev/null --max-time 1 "http://localhost:${port}${path}" 2>/dev/null && return 0
    return 1
}

open_url() {
    if command -v open >/dev/null 2>&1; then
        open "$1"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$1" >/dev/null 2>&1
    else
        echo "Open $1 in your browser."
    fi
}

echo "SG Expenditure Tracker"
echo "-----------------------"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: 'uv' is not installed or not on PATH. Install it from https://docs.astral.sh/uv/" >&2
    exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: 'npm' is not installed or not on PATH. Install Node.js from https://nodejs.org/" >&2
    exit 1
fi

windows_opened=0

# --- Backend -------------------------------------------------------------
if port_up 8000 "/api/health"; then
    echo "Backend already running on port 8000 - leaving it as is."
else
    echo "Starting backend (http://127.0.0.1:8000)..."
    (cd "$backend_dir" && uv sync && exec uv run uvicorn app.main:app --reload) >"$backend_log" 2>&1 &
    backend_pid=$!
    windows_opened=$((windows_opened + 1))
fi

# --- Frontend --------------------------------------------------------------
if port_up 5173; then
    echo "Frontend already running on port 5173 - leaving it as is."
else
    echo "Starting frontend (http://localhost:5173)..."
    if [ ! -d "$frontend_dir/node_modules" ]; then
        (cd "$frontend_dir" && npm install && exec npm run dev) >"$frontend_log" 2>&1 &
    else
        (cd "$frontend_dir" && exec npm run dev) >"$frontend_log" 2>&1 &
    fi
    frontend_pid=$!
    windows_opened=$((windows_opened + 1))
fi

# --- Wait for both, then open the browser -----------------------------------
echo "Waiting for both servers to come up (first run can take a minute for npm install)..."
backend_ready=false
frontend_ready=false
for _ in $(seq 1 60); do
    [ "$backend_ready" = false ] && port_up 8000 "/api/health" && backend_ready=true
    [ "$frontend_ready" = false ] && port_up 5173 && frontend_ready=true
    [ "$backend_ready" = true ] && [ "$frontend_ready" = true ] && break
    sleep 1
done
[ "$backend_ready" = false ] && echo "Backend didn't respond within 60s - check $backend_log for errors."
[ "$frontend_ready" = false ] && echo "Frontend didn't respond within 60s - check $frontend_log for errors."

[ "$frontend_ready" = true ] && open_url "http://localhost:5173"

echo ""
if [ "$windows_opened" -gt 0 ]; then
    echo "Logs: $backend_log / $frontend_log"
    echo "Press Ctrl+C to stop the server(s) this script started."
    tail -f "$backend_log" "$frontend_log" &
    tail_pid=$!
    wait "$tail_pid"
else
    echo "Both servers were already running - nothing new to start."
fi
