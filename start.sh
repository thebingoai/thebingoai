#!/bin/bash
# Local development startup script.
# Starts all services via docker/local/docker-compose.yml.
# Auto-detects database mode from DATABASE_URL in .env:
#   - Supabase/external DB: skips Docker PostgreSQL
#   - localhost/postgres: includes Docker PostgreSQL via override file
#
# Usage: ./start.sh

set -e

COMPOSE_FILE="docker/local/docker-compose.yml"
COMPOSE_POSTGRES="docker/local/docker-compose.postgres.yml"

echo "Starting LLM-MD-CLI (local dev)..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo ".env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your API keys, then re-run ./start.sh"
    exit 1
fi

# Read DATABASE_URL from .env (ignore comments and whitespace)
DATABASE_URL=$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d'=' -f2-)

# Build compose command based on database mode
COMPOSE_CMD="docker compose -f $COMPOSE_FILE"
if [[ "$DATABASE_URL" == *"localhost"* ]] || [[ "$DATABASE_URL" == *"@postgres:"* ]]; then
    COMPOSE_CMD="$COMPOSE_CMD -f $COMPOSE_POSTGRES"
    echo "Using local PostgreSQL (Docker)..."
else
    echo "Using external database (Supabase)..."
fi

# Stop services on Ctrl+C
trap "echo ''; echo 'Stopping services...'; $COMPOSE_CMD down; exit 0" INT TERM

# Start all services (backend builds first, frontend waits for backend health)
echo "Starting all services..."
$COMPOSE_CMD up -d

# Wait for backend health check
echo "Waiting for backend to be ready..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "Backend failed to start. Check logs:"
        echo "  $COMPOSE_CMD logs backend"
        $COMPOSE_CMD down
        exit 1
    fi
    sleep 2
done

echo ""
echo "All services running:"
echo "  Frontend:   http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo ""
echo "Useful commands:"
echo "  Logs:    $COMPOSE_CMD logs -f [service]"
echo "  Restart: $COMPOSE_CMD restart [service]"
echo "  Stop:    $COMPOSE_CMD down"
echo ""
echo "Press Ctrl+C to stop all services."

# Follow logs so the terminal stays active (Ctrl+C triggers the trap above)
$COMPOSE_CMD logs -f
