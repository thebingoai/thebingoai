#!/bin/bash
# Fix Docker proxy configuration

echo "🔧 Configuring Docker to bypass proxy for Docker Hub..."

# Create Docker daemon config directory
mkdir -p ~/.docker

# Create daemon.json with registry mirrors (bypasses proxy)
cat > ~/.docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.gcr.io",
    "https://registry.docker-cn.com",
    "https://hub-mirror.c.163.com"
  ],
  "proxies": {
    "default": {
      "httpProxy": "",
      "httpsProxy": "",
      "noProxy": "*.docker.io,*.docker.com,docker.io,registry-1.docker.io"
    }
  }
}
EOF

echo "✅ Docker config updated"
echo "⚠️  Please RESTART Docker Desktop for changes to take effect"
echo ""
echo "Steps:"
echo "1. Quit Docker Desktop (Cmd+Q)"
echo "2. Wait 5 seconds"
echo "3. Reopen Docker Desktop"
echo "4. Wait for 'Engine running'"
echo "5. Run: ./docker-test.sh"
