#!/usr/bin/env bash
# ============================================================
#  OASIS — Run Script
#  Starts the FastAPI backend and opens the frontend dashboards.
# ============================================================

set -euo pipefail

# ---- Config ----
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- Colors ----
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

# ---- Helpers ----
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ---- Banner ----
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  OASIS — Energy Intelligence Platform${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# ---- Navigate to OASIS directory ----
cd "$SCRIPT_DIR"
info "Working directory: $SCRIPT_DIR"

# ============================================================
# Environment setup and dependency installation
# are intentionally skipped.
#
# The system Python/environment is assumed to already contain
# all required OASIS dependencies.
# ============================================================

# ---- Start backend ----
info "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
echo ""

uvicorn backend.main:app \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" \
    --reload \
    --reload-dir modules \
    --reload-dir backend &

BACKEND_PID=$!
info "Backend PID: $BACKEND_PID"

# ---- Start the Next.js frontend (best-effort) ----
FRONTEND_PID=""
FRONTEND_PORT="3000"

if [ -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    info "Starting Next.js frontend on http://localhost:${FRONTEND_PORT} ..."
    ( cd "$SCRIPT_DIR/frontend" && npm run dev -- --port "$FRONTEND_PORT" ) &
    FRONTEND_PID=$!
    info "Frontend PID: $FRONTEND_PID"
else
    warn "frontend/node_modules not found — skipping the UI."
    warn "Run 'npm install' in frontend/ and then 'npm run dev'."
fi

# ---- Wait for backend to be ready ----
info "Waiting for backend to start..."

for i in $(seq 1 30); do
    if curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
        ok "Backend is healthy!"
        break
    fi

    sleep 1

    if [ "$i" -eq 30 ]; then
        warn "Backend may not be ready yet. Check http://${BACKEND_HOST}:${BACKEND_PORT}"
    fi
done

# ---- Open frontend ----
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  OASIS is running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  Backend API:   ${CYAN}http://${BACKEND_HOST}:${BACKEND_PORT}${NC}"
echo -e "  API Docs:      ${CYAN}http://${BACKEND_HOST}:${BACKEND_PORT}/docs${NC}"
if [ -n "$FRONTEND_PID" ]; then
    echo -e "  Web UI:        ${CYAN}http://localhost:${FRONTEND_PORT}${NC}"
else
    echo -e "  Web UI:        ${YELLOW}not started (run 'npm run dev' in frontend/)${NC}"
fi
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop the backend.${NC}"
echo ""

# ---- Open a browser at the UI (best-effort) ----
UI_URL="http://localhost:${FRONTEND_PORT}"
if [ -z "$FRONTEND_PID" ]; then
    # No UI: the API docs are the most useful landing page.
    UI_URL="http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
fi

if command -v start &>/dev/null; then
    start "" "$UI_URL" 2>/dev/null || true
elif command -v open &>/dev/null; then
    open "$UI_URL" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then
    xdg-open "$UI_URL" 2>/dev/null || true
fi

# ---- Cleanup on exit ----
cleanup() {
    echo ""
    info "Shutting down backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true

    if [ -n "$FRONTEND_PID" ]; then
        info "Shutting down frontend (PID $FRONTEND_PID)..."
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi

    ok "Stopped."
}

trap cleanup EXIT INT TERM

# ---- Keep script alive until Ctrl+C ----
wait "$BACKEND_PID" 2>/dev/null || true