#!/bin/bash
# First-time SSL certificate setup using Let's Encrypt / certbot
# Run this ONCE from the project root before starting production services.
#
# Usage:
#   ./docker/production/init-ssl.sh <domain> <email>
# Or with environment variables:
#   DOMAIN=example.com EMAIL=admin@example.com ./docker/production/init-ssl.sh

set -e

DOMAIN="${1:-${DOMAIN}}"
EMAIL="${2:-${EMAIL}}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Error: DOMAIN and EMAIL are required."
    echo ""
    echo "Usage:"
    echo "  $0 <domain> <email>"
    echo "  DOMAIN=example.com EMAIL=admin@example.com $0"
    exit 1
fi

COMPOSE_FILE="docker/production/docker-compose.yml"
TEMPLATE="docker/production/nginx/conf.d/app.conf.template"
APP_CONF="docker/production/nginx/conf.d/app.conf"

echo "=== SSL Initialization for $DOMAIN ==="
echo ""

# 1. Start only nginx (HTTP mode via default.conf for ACME challenge)
echo "[1/4] Starting nginx in HTTP mode..."
docker compose -f "$COMPOSE_FILE" up -d nginx

sleep 3  # Give nginx a moment to start

# 2. Obtain certificate via certbot webroot challenge
echo "[2/4] Obtaining SSL certificate from Let's Encrypt..."
docker compose -f "$COMPOSE_FILE" run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# 3. Generate app.conf from template, substituting DOMAIN
echo "[3/4] Generating nginx HTTPS config..."
DOMAIN="$DOMAIN" envsubst '${DOMAIN}' < "$TEMPLATE" > "$APP_CONF"
echo "  Created: $APP_CONF"

# 4. Reload nginx to pick up HTTPS config
echo "[4/4] Reloading nginx with HTTPS config..."
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo ""
echo "=== SSL setup complete! ==="
echo ""
echo "Your site is accessible at: https://$DOMAIN"
echo ""
echo "Next steps:"
echo "  Start all services: docker compose -f $COMPOSE_FILE up -d"
echo "  View logs:          docker compose -f $COMPOSE_FILE logs -f"
echo ""
echo "Certificate auto-renewal is handled by the certbot service (runs every 12h)."
