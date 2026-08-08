#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[HEALTH]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

FAILED=0
COMPOSE_FILE="docker-compose.prod.yml"

echo "========================================="
echo "  AI CFO Manager - Health Check"
echo "========================================="
echo ""

# --- Backend ---
echo "--- Backend ---"
if docker compose -f "$COMPOSE_FILE" exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    log "Backend API: UP"
    docker compose -f "$COMPOSE_FILE" exec -T backend curl -s http://localhost:8000/health
    echo ""
else
    fail "Backend API: DOWN"
    FAILED=$((FAILED + 1))
fi

# --- Frontend ---
echo ""
echo "--- Frontend ---"
if docker compose -f "$COMPOSE_FILE" exec -T frontend wget -q --spider http://127.0.0.1:3000/ > /dev/null 2>&1; then
    log "Frontend: UP"
else
    fail "Frontend: DOWN"
    FAILED=$((FAILED + 1))
fi

# --- Nginx ---
echo ""
echo "--- Nginx ---"
if docker compose -f "$COMPOSE_FILE" exec -T nginx wget -q --spider http://127.0.0.1:80/health > /dev/null 2>&1; then
    log "Nginx: UP"
else
    fail "Nginx: DOWN"
    FAILED=$((FAILED + 1))
fi

# --- PostgreSQL ---
echo ""
echo "--- PostgreSQL ---"
if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    log "PostgreSQL: UP"
else
    fail "PostgreSQL: DOWN"
    FAILED=$((FAILED + 1))
fi

# --- Redis ---
echo ""
echo "--- Redis ---"
if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
    log "Redis: UP"
else
    fail "Redis: DOWN"
    FAILED=$((FAILED + 1))
fi

# --- Celery Worker ---
echo ""
echo "--- Celery Worker ---"
if docker compose -f "$COMPOSE_FILE" exec -T celery-worker celery -A app.tasks.celery_app:celery_app inspect ping --timeout 5 > /dev/null 2>&1; then
    log "Celery Worker: UP"
else
    warn "Celery Worker: Could not ping (may still be starting)"
fi

# --- Docker container status ---
echo ""
echo "--- Container Status ---"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "========================================="
if [ "$FAILED" -gt 0 ]; then
    fail "Health check FAILED ($FAILED service(s) down)"
    exit 1
else
    log "All services are HEALTHY"
fi
