#!/bin/bash
# Docker setup and test script for LLM-MD-CLI

set -e

echo "🐳 LLM-MD-CLI Docker Setup"
echo ""

# Check if .env has OpenAI key
if grep -q "OPENAI_API_KEY=sk-proj-xxxxxxxx" /Users/edmund/work/llm-md-cli/.env; then
    echo "⚠️  Please update OPENAI_API_KEY in .env file with your actual key"
    echo "   Current placeholder detected."
    exit 1
fi

cd /Users/edmund/work/llm-md-cli

echo "📦 Building and starting Docker containers..."
docker-compose down 2>/dev/null || true
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Wait for backend health
echo "🔍 Checking backend health..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "✅ Backend is ready!"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "📰 Preparing test data (news)..."
python3 scripts/convert_news.py

echo ""
echo "☁️  Uploading news to Pinecone..."
cd cli
pip install -q -e .

# Configure CLI to use Docker backend
mdcli config set-backend http://localhost:8000

# Upload the news file
mdcli upload ../test_data/news-2026-02-06.md --namespace=news --tag="tech-news"

echo ""
echo "🔍 Testing search..."
mdcli query "What AI models were released?" --namespace=news --top-k=3

echo ""
echo "💬 Testing RAG chat..."
mdcli chat "Summarize the main AI news from today" --namespace=news --stream

echo ""
echo "✅ All tests complete!"
echo ""
echo "🐳 Docker services running:"
echo "   Backend: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Redis: localhost:6379"
echo ""
echo "📊 To check status:"
echo "   docker-compose ps"
echo ""
echo "🛑 To stop:"
echo "   docker-compose down"
