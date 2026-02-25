#!/bin/bash
# Startup script for LLM-MD-CLI (Docker backend + native frontend)

set -e

echo "Starting LLM-MD-CLI services..."

# Check if .env exists
if [ ! -f .env ]; then
    echo ".env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your API keys before continuing"
    exit 1
fi

# Start backend services via Docker
echo "Starting backend services with Docker Compose..."
docker-compose up -d

# Wait for backend health check
echo "Waiting for backend to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "Backend failed to start. Check logs with: docker-compose logs backend"
        docker-compose down
        exit 1
    fi
    sleep 2
done

# Start frontend
if [ -f "frontend/package.json" ]; then
    echo "Setting up frontend..."
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install
    fi

    echo ""
    echo "Services running:"
    echo "  Backend API:  http://localhost:8000"
    echo "  API Docs:     http://localhost:8000/docs"
    echo "  Frontend:     http://localhost:3000"
    echo ""
    echo "Press Ctrl+C to stop all services"
    echo ""

    # Trap SIGINT to stop Docker services when frontend exits
    trap "echo ''; echo 'Stopping services...'; cd ..; docker-compose down; exit 0" INT

    npm run dev
else
    echo ""
    echo "Services running:"
    echo "  Backend API:  http://localhost:8000"
    echo "  API Docs:     http://localhost:8000/docs"
    echo "  Health:       http://localhost:8000/health"
    echo ""
    echo "Press Ctrl+C to stop all services"
    echo ""

    trap "echo ''; echo 'Stopping services...'; docker-compose down; exit 0" INT
    wait
fi
