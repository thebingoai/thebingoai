#!/bin/bash
# Local development startup script.
# Starts all services (backend + frontend) via docker/local/docker-compose.yml.
#
# Usage: ./start.sh

set -e

COMPOSE_FILE="docker/local/docker-compose.yml"

echo "Starting LLM-MD-CLI (local dev)..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo ".env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your API keys, then re-run ./start.sh"
    exit 1
fi

# Stop services on Ctrl+C
trap "echo ''; echo 'Stopping services...'; docker compose -f '$COMPOSE_FILE' down; exit 0" INT TERM

# Start all services (backend builds first, frontend waits for backend health)
echo "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for backend health check
echo "Waiting for backend to be ready..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "Backend failed to start. Check logs:"
        echo "  docker compose -f $COMPOSE_FILE logs backend"
        docker compose -f "$COMPOSE_FILE" down
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
echo "  Logs:    docker compose -f $COMPOSE_FILE logs -f [service]"
echo "  Restart: docker compose -f $COMPOSE_FILE restart [service]"
echo "  Stop:    docker compose -f $COMPOSE_FILE down"
echo ""
echo "Press Ctrl+C to stop all services."

# Follow logs so the terminal stays active (Ctrl+C triggers the trap above)
docker compose -f "$COMPOSE_FILE" logs -f
