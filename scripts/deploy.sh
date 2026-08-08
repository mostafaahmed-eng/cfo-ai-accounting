#!/bin/bash
set -euo pipefail

ENVIRONMENT=${1:-staging}
COMPOSE_FILE="docker-compose.prod.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; exit 1; }

# --- Preflight checks ---
command -v docker >/dev/null 2>&1 || error "docker is not installed"
command -v docker compose >/dev/null 2>&1 || error "docker compose is not available"
[ -f "$COMPOSE_FILE" ] || error "$COMPOSE_FILE not found"

if [ ! -f ".env" ]; then
    warn ".env file not found, copying from .env.example"
    cp .env.example .env
    error "Please edit .env with your production values before deploying"
fi

log "Deploying to ${ENVIRONMENT}..."

# --- Build ---
log "Building images..."
docker compose -f "$COMPOSE_FILE" build --no-cache

# --- Database migration ---
log "Running database migrations..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis
sleep 5
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

# --- Deploy services ---
log "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# --- Health check ---
# The backend/frontend containers publish no host ports, so health checks run
# inside the compose network via `docker compose exec` (reachable from this
# script's context) instead of curling host ports.
log "Waiting for backend to become healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
until docker compose -f "$COMPOSE_FILE" exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        docker compose -f "$COMPOSE_FILE" ps
        error "Backend health check failed after ${MAX_RETRIES} attempts"
    fi
    warn "Waiting for backend... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 2
done

# Recreate of the backend/frontend containers assigns new container IPs. nginx
# resolves upstream hostnames at startup, so force it to re-resolve the current
# addresses (graceful, no downtime).
log "Refreshing nginx upstream DNS..."
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload > /dev/null 2>&1 \
    || warn "nginx reload failed; stale upstream DNS may persist until the next restart"

log "Running full health check..."
bash scripts/health-check.sh

log "Deployment complete!"
