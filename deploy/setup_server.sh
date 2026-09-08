#!/usr/bin/env bash
# ==============================================================================
# Recraftr Production Server Provisioning & Hardening Script
# Target OS: Ubuntu 22.04 LTS / 24.04 LTS
# ==============================================================================
set -euo pipefail

echo "==> Starting Recraftr Server Setup..."

# 1. Require root execution
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (or with sudo)." >&2
   exit 1
fi

# 2. System updates & package installation
echo "==> Updating apt packages..."
apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    curl \
    git \
    ufw \
    fail2ban \
    unattended-upgrades \
    nginx \
    logrotate \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates

# 3. Enable automatic security updates
echo "==> Enabling unattended security upgrades..."
dpkg-reconfigure -f noninteractive unattended-upgrades

# 4. Create non-root system user 'recraftr'
if id "recraftr" &>/dev/null; then
    echo "==> User 'recraftr' already exists."
else
    echo "==> Creating system user 'recraftr'..."
    adduser --system --group --home /var/www/recraftr --shell /bin/bash recraftr
fi

# 5. Directory structure & permissions
echo "==> Setting up application and log directories..."
mkdir -p /var/www/recraftr
mkdir -p /var/log/recraftr
chown -R recraftr:recraftr /var/www/recraftr
chown -R recraftr:recraftr /var/log/recraftr
chmod 750 /var/www/recraftr
chmod 750 /var/log/recraftr

# 6. Configure UFW Firewall
echo "==> Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing

# Allow standard SSH (port 22) - modify if using custom SSH port
ufw allow 22/tcp comment 'SSH access'

# Allow Web Traffic
ufw allow 80/tcp comment 'HTTP (Let'\''s Encrypt / Certbot & SSL redirect)'
ufw allow 443/tcp comment 'HTTPS production traffic'

# Explicitly block direct public access to FastAPI and internal databases
ufw deny 8000/tcp comment 'Block direct public FastAPI access'
ufw deny 5432/tcp comment 'Block direct public PostgreSQL access'
ufw deny 27017/tcp comment 'Block direct public MongoDB access'

# Enable firewall without interactive prompt
echo "y" | ufw enable
ufw status verbose

# 7. Configure Fail2ban for SSH brute-force defense
echo "==> Configuring Fail2ban..."
systemctl enable fail2ban
systemctl restart fail2ban

# 8. Install Systemd Service Unit
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/recraftr-backend.service" ]; then
    echo "==> Installing systemd service..."
    cp "$SCRIPT_DIR/recraftr-backend.service" /etc/systemd/system/recraftr-backend.service
    systemctl daemon-reload
    systemctl enable recraftr-backend.service
fi

# 9. Install Logrotate Configuration
if [ -f "$SCRIPT_DIR/recraftr.logrotate" ]; then
    echo "==> Installing logrotate config..."
    cp "$SCRIPT_DIR/recraftr.logrotate" /etc/logrotate.d/recraftr
    chmod 644 /etc/logrotate.d/recraftr
fi

# 10. Install Nginx Configuration
if [ -f "$SCRIPT_DIR/nginx.conf" ]; then
    echo "==> Installing Nginx configuration..."
    cp "$SCRIPT_DIR/nginx.conf" /etc/nginx/sites-available/recraftr.conf
    ln -sf /etc/nginx/sites-available/recraftr.conf /etc/nginx/sites-enabled/recraftr.conf
    # Note: Test with 'nginx -t' after configuring SSL certificates
fi

echo "=============================================================================="
echo "==> Recraftr Server Provisioning Complete!"
echo "=============================================================================="
echo "Next Steps:"
echo " 1. Put backend code and virtualenv in /var/www/recraftr/backend"
echo " 2. Populate /var/www/recraftr/backend/.env with production credentials"
echo " 3. Obtain SSL certificates via Certbot:"
echo "    certbot certonly --nginx -d api.recraftr.com"
echo " 4. Test Nginx config: nginx -t && systemctl reload nginx"
echo " 5. Start Backend service: systemctl start recraftr-backend"
echo " 6. Verify SSH hardening in /etc/ssh/sshd_config:"
echo "    PermitRootLogin no"
echo "    PasswordAuthentication no"
echo "=============================================================================="
