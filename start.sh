#!/bin/bash
# Startup script for LLM-MD-CLI

set -e

echo "🚀 Starting LLM-MD-CLI services..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "❌ Please edit .env with your API keys before continuing"
    exit 1
fi

# Check Python environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Check Redis
echo "🔍 Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis not running. Please start Redis:"
    echo "   brew services start redis  # macOS"
    echo "   sudo service redis start   # Linux"
    exit 1
fi
echo "✅ Redis is running"

# Start Celery worker in background
echo "🥬 Starting Celery worker..."
celery -A backend.tasks.upload_tasks worker --loglevel=info &
CELERY_PID=$!
echo "   Celery PID: $CELERY_PID"

# Start backend
echo "🌐 Starting FastAPI backend..."
echo "   API docs: http://localhost:8000/docs"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!
echo "   Uvicorn PID: $UVICORN_PID"

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service Status:"
echo "   Backend: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Health: http://localhost:8000/health"
echo ""
echo "🛑 To stop, press Ctrl+C or run: kill $CELERY_PID $UVICORN_PID"
echo ""

# Wait for interrupt
trap "echo 'Stopping services...'; kill $CELERY_PID $UVICORN_PID 2>/dev/null; exit 0" INT
wait
