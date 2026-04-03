#!/bin/bash
# Zero-downtime production deployment script.
# Run from the project root on the production server.
#
# Usage: ./deploy.sh

set -e

COMPOSE_FILE="docker/production/docker-compose.yml"

echo "=== Production Deployment ==="
echo ""

# 1. Pull latest code
echo "[1/6] Pulling latest code from main..."
git pull origin main

# 2. Build new images without stopping running containers
echo "[2/6] Building new images..."
docker compose -f "$COMPOSE_FILE" build

# 3. Rolling update: backend
echo "[3/6] Updating backend..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps backend

echo "  Waiting for backend health check..."
for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" exec backend \
        python3 -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" 2>/dev/null; then
        echo "  Backend is healthy."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ERROR: Backend health check failed after 60s. Check logs:"
        echo "    docker compose -f $COMPOSE_FILE logs backend"
        exit 1
    fi
    sleep 2
done

# 4. Update Celery workers
echo "[4/6] Updating Celery workers..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps celery-worker celery-beat

# 5. Rebuild frontend static files and reload nginx
echo "[5/6] Updating frontend..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps frontend
echo "  Waiting for frontend static files to be ready..."
sleep 10
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload
echo "  Nginx reloaded with new frontend assets."

# 6. Clean up dangling images
echo "[6/6] Cleaning up old images..."
docker image prune -f

echo ""
echo "=== Deployment complete! ==="
