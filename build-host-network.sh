#!/bin/bash
# Build using host network (bypasses Docker proxy)

echo "🐳 Building with host network..."

# Export empty proxy to disable
cd /Users/edmund/work/llm-md-cli

# Build with host network and no proxy
HTTP_PROXY="" \
HTTPS_PROXY="" \
NO_PROXY="*" \
docker build \
  --network=host \
  --build-arg HTTP_PROXY="" \
  --build-arg HTTPS_PROXY="" \
  --progress=plain \
  -t llm-md-cli-backend:latest \
  .

echo "✅ Build complete"
