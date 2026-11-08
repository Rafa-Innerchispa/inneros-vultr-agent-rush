#!/usr/bin/env bash
set -euo pipefail

echo "=== Deploying InnerOS Verified Operations v0.6.0 to Vultr ==="

TARGET_DIR="/opt/inneros-vultr-agent-rush"
mkdir -p "$TARGET_DIR"

# Install system dependencies
apt-get update -y
apt-get install -y python3 python3-pip python3-venv caddy ufw

# Set up UFW firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Copy service and caddy configuration
cp "$TARGET_DIR/infra/inneros-verified-ops.service" /etc/systemd/system/inneros-verified-ops.service
cp "$TARGET_DIR/infra/Caddyfile" /etc/caddy/Caddyfile

systemctl daemon-reload
systemctl enable --now inneros-verified-ops.service
systemctl reload caddy || systemctl restart caddy

echo "=== Deployment Complete! ==="
curl -s http://127.0.0.1:8792/health || true
