#!/bin/bash
# Startup script for LLM-MD-CLI (Backend + Frontend)

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

echo "📦 Installing backend dependencies..."
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
celery -A backend.tasks.upload_tasks worker --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo "   Celery PID: $CELERY_PID"

# Start backend
echo "🌐 Starting FastAPI backend..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "⏳ Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start. Check logs/backend.log"
        kill $CELERY_PID $BACKEND_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Check if frontend exists and is set up
FRONTEND_PID=""
if [ -f "frontend/package.json" ]; then
    echo "🎨 Setting up frontend..."
    cd frontend

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        npm install
    fi

    # Start frontend dev server
    echo "🎨 Starting Nuxt frontend..."
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo "   Frontend PID: $FRONTEND_PID"

    # Wait for frontend to be ready
    echo "⏳ Waiting for frontend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            echo "✅ Frontend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "⚠️  Frontend may not be ready. Check logs/frontend.log"
        fi
        sleep 1
    done
else
    echo "ℹ️  Frontend not yet set up (no package.json found)"
    echo "   Backend will be available for API requests"
fi

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Service Status:"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Health: http://localhost:8000/health"

if [ -n "$FRONTEND_PID" ]; then
    echo "   Frontend: http://localhost:3000"
    echo ""
    echo "🛑 To stop all services: kill $CELERY_PID $BACKEND_PID $FRONTEND_PID"
else
    echo ""
    echo "🛑 To stop services: kill $CELERY_PID $BACKEND_PID"
fi

echo ""
echo "📋 Logs available at:"
echo "   Backend: logs/backend.log"
echo "   Celery: logs/celery.log"
if [ -n "$FRONTEND_PID" ]; then
    echo "   Frontend: logs/frontend.log"
fi
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Wait for interrupt
trap "echo ''; echo 'Stopping services...'; kill $CELERY_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
