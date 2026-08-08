#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; exit 1; }

COMPOSE_FILE="docker-compose.prod.yml"

log "Rolling back to previous version..."

# Find the previous git tag
PREV_TAG=$(git describe --tags --abbrev=0 HEAD~1 2>/dev/null || echo "")
if [ -n "$PREV_TAG" ]; then
    log "Rolling back to tag: $PREV_TAG"
    git checkout "$PREV_TAG"
else
    PREV_COMMIT=$(git rev-parse HEAD~1 2>/dev/null || echo "")
    if [ -z "$PREV_COMMIT" ]; then
        error "No previous version found to roll back to"
    fi
    warn "No previous tag found, rolling back to commit: $PREV_COMMIT"
    git checkout "$PREV_COMMIT"
fi

# Pull images and restart
log "Pulling images..."
docker compose -f "$COMPOSE_FILE" pull

log "Running migrations..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis
sleep 5
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

log "Restarting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# Health check (exec-based: backend publishes no host port)
MAX_RETRIES=30
RETRY_COUNT=0
until docker compose -f "$COMPOSE_FILE" exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        docker compose -f "$COMPOSE_FILE" ps
        error "Rollback failed! Backend health check failed after ${MAX_RETRIES} attempts."
    fi
    log "Waiting for backend... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 2
done

log "Refreshing nginx upstream DNS..."
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload > /dev/null 2>&1 \
    || warn "nginx reload failed; stale upstream DNS may persist until the next restart"

log "Rollback successful! Backend is healthy."
bash scripts/health-check.sh
