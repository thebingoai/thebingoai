#!/bin/bash
# Build Docker without proxy

# Unset proxy environment variables
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy

# Build with --build-arg to pass empty proxy
docker build \
  --build-arg HTTP_PROXY="" \
  --build-arg HTTPS_PROXY="" \
  --build-arg http_proxy="" \
  --build-arg https_proxy="" \
  -t llm-md-cli-backend:latest \
  .

echo "✅ Build complete (without proxy)"
