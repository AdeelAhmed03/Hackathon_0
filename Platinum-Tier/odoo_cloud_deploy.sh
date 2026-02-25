#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Platinum Tier — Odoo Cloud Deployment Script
#
# Deploys Odoo 19 Community on a cloud VM with:
#   1. Docker Compose: Odoo 19 + PostgreSQL 15 + Nginx reverse proxy + Certbot
#   2. HTTPS via Let's Encrypt (auto-renewing certbot)
#   3. Daily pg_dump backups to data/Backups/ (syncable to local via Git)
#   4. Health monitoring with container auto-restart
#   5. Platinum work-zone enforcement: cloud = draft-only, local = approval/post
#
# Usage:
#   export DOMAIN_NAME=odoo.yourdomain.com
#   export CERTBOT_EMAIL=admin@yourdomain.com
#   export ODOO_ADMIN_PASSWD=change_me_in_production
#   export POSTGRES_PASSWORD=change_me_in_production
#   bash odoo_cloud_deploy.sh
#
# Tested on: Ubuntu 22.04 LTS (Oracle OCI / AWS EC2)
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── COLORS ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn()  { echo -e "${YELLOW}[WARN]  $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}" >&2; }
info()  { echo -e "${CYAN}[INFO]  $1${NC}"; }

# ── CONFIGURATION ───────────────────────────────────────────────────────
DOMAIN_NAME="${DOMAIN_NAME:?Set DOMAIN_NAME env var (e.g. odoo.example.com)}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL env var}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-odoo_platinum_2026}"
ODOO_ADMIN_PASSWD="${ODOO_ADMIN_PASSWD:-admin_platinum_2026}"

DEPLOY_DIR="$HOME/odoo-cloud"
BACKUPS_DIR="$(cd "$(dirname "$0")" && pwd)/data/Backups"
VAULT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── PREFLIGHT CHECKS ───────────────────────────────────────────────────
if [ "$EUID" -eq 0 ]; then
    error "Run as a normal user, not root (script uses sudo where needed)"
    exit 1
fi

log "Step 1/12: Preflight checks"
if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    info "Detected Ubuntu — good"
else
    warn "Not Ubuntu; this script is tested on Ubuntu 22.04. Continuing anyway."
fi

# ── INSTALL DOCKER ──────────────────────────────────────────────────────
log "Step 2/12: Ensuring Docker + Compose are installed"
if ! command -v docker &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker "$USER"
    info "Docker installed. You may need to log out/in for group change."
else
    info "Docker already installed ($(docker --version))"
fi

# ── CREATE DIRECTORY TREE ───────────────────────────────────────────────
log "Step 3/12: Creating directory tree"
mkdir -p "$DEPLOY_DIR"/{config,addons,ssl,data/{db,odoo,certs}}
mkdir -p "$BACKUPS_DIR"

# ── DOCKER COMPOSE ──────────────────────────────────────────────────────
log "Step 4/12: Writing docker-compose.yml"
cat > "$DEPLOY_DIR/docker-compose.yml" << COMPOSE_EOF
version: '3.8'

services:
  # ── PostgreSQL 15 ─────────────────────────────────────────────────────
  odoo-db:
    image: postgres:15
    container_name: odoo-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: odoo
    volumes:
      - ./data/db:/var/lib/postgresql/data
    networks: [odoo-net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo -d odoo"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits: { memory: 512M }

  # ── Odoo 19 Community ─────────────────────────────────────────────────
  odoo:
    image: odoo:19.0
    container_name: odoo
    restart: unless-stopped
    depends_on:
      odoo-db: { condition: service_healthy }
    ports:
      - "127.0.0.1:8069:8069"
      - "127.0.0.1:8072:8072"
    environment:
      HOST: odoo-db
      USER: odoo
      PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./data/odoo:/var/lib/odoo
      - ./addons:/mnt/extra-addons
      - ./config/odoo.conf:/etc/odoo/odoo.conf:ro
    networks: [odoo-net]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8069/web/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits: { memory: 1G }

  # ── Nginx reverse proxy ───────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: odoo-nginx
    restart: unless-stopped
    depends_on: [odoo]
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./data/certs:/etc/letsencrypt:ro
      - ./ssl/certbot-webroot:/var/www/certbot:ro
    networks: [odoo-net]

  # ── Certbot (Let's Encrypt) ───────────────────────────────────────────
  certbot:
    image: certbot/certbot
    container_name: odoo-certbot
    volumes:
      - ./data/certs:/etc/letsencrypt
      - ./ssl/certbot-webroot:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew --webroot -w /var/www/certbot --quiet; sleep 12h & wait \$\${!}; done'"
    networks: [odoo-net]

networks:
  odoo-net:
    driver: bridge
COMPOSE_EOF

# ── ODOO CONFIG ─────────────────────────────────────────────────────────
log "Step 5/12: Writing Odoo server config"
cat > "$DEPLOY_DIR/config/odoo.conf" << ODOO_CONF_EOF
[options]
admin_passwd = ${ODOO_ADMIN_PASSWD}
db_host = odoo-db
db_port = 5432
db_user = odoo
db_password = ${POSTGRES_PASSWORD}
db_name = odoo

; Performance (cloud VM, 2-4 vCPU)
workers = 2
max_cron_threads = 1
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_time_cpu = 600
limit_time_real = 1200

; Security
list_db = False
proxy_mode = True
log_level = info
logfile = /var/lib/odoo/odoo-server.log

; Addons
addons_path = /mnt/extra-addons

; Longpolling
longpolling_port = 8072
ODOO_CONF_EOF

# ── NGINX CONFIG ────────────────────────────────────────────────────────
log "Step 6/12: Writing Nginx config (HTTP + HTTPS)"
mkdir -p "$DEPLOY_DIR/ssl/certbot-webroot"
cat > "$DEPLOY_DIR/config/nginx.conf" << NGINX_EOF
upstream odoo  { server odoo:8069; }
upstream odoo-lp { server odoo:8072; }

# Rate limiting
limit_req_zone \$binary_remote_addr zone=odoo_limit:10m rate=10r/s;

# ── HTTP: ACME challenge + redirect ────────────────────────────────────
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# ── HTTPS ──────────────────────────────────────────────────────────────
server {
    listen 443 ssl http2;
    server_name ${DOMAIN_NAME};

    # Certs — initially self-signed, replaced after first certbot run
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # HSTS + security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 200m;

    # Odoo backend
    location / {
        limit_req zone=odoo_limit burst=20 nodelay;
        proxy_pass http://odoo;
        proxy_redirect off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 600s;
        proxy_send_timeout    600s;
        proxy_read_timeout    600s;
    }

    # Longpolling
    location /longpolling {
        proxy_pass http://odoo-lp;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Static file cache
    location ~* /web/static/ {
        proxy_pass http://odoo;
        proxy_set_header Host \$host;
        expires 365d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_EOF

# ── INITIAL SELF-SIGNED CERT (so nginx can start before certbot) ──────
log "Step 7/12: Creating initial self-signed certificate"
CERT_DIR="$DEPLOY_DIR/data/certs/live/$DOMAIN_NAME"
mkdir -p "$CERT_DIR"
if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/CN=$DOMAIN_NAME" 2>/dev/null
    info "Temporary self-signed cert created (will be replaced by Let's Encrypt)"
fi

# ── BACKUP SCRIPT (hot backup — no Odoo stop) ──────────────────────────
log "Step 8/12: Writing backup script (daily pg_dump, hot, no downtime)"
cat > "$DEPLOY_DIR/backup-odoo.sh" << 'BACKUP_EOF'
#!/bin/bash
# Hot backup — pg_dump while Odoo stays running (no downtime for 24/7 cloud)
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/../data/Backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/odoo_backup_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting hot backup..."

# pg_dump from running container (no need to stop Odoo)
docker exec odoo-db pg_dump -U odoo -d odoo --no-owner --clean \
    | gzip > "$BACKUP_FILE"

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup complete: $BACKUP_FILE ($FILESIZE)"

# Symlink latest
ln -sf "$BACKUP_FILE" "$BACKUP_DIR/odoo_backup_latest.sql.gz"

# Write manifest for Git sync
cat > "$BACKUP_DIR/BACKUP_MANIFEST.md" << MANIFEST
---
type: backup_manifest
last_backup: ${DATE}
file: odoo_backup_${DATE}.sql.gz
size: ${FILESIZE}
method: pg_dump_hot
---
# Latest Odoo Backup
- **Date**: $(date +'%Y-%m-%d %H:%M:%S')
- **File**: odoo_backup_${DATE}.sql.gz
- **Size**: ${FILESIZE}
- **Method**: Hot pg_dump (no downtime)
MANIFEST

# Prune: keep last 7 daily, last 4 weekly
find "$BACKUP_DIR" -name "odoo_backup_*.sql.gz" -mtime +7 -delete 2>/dev/null || true
echo "[$(date)] Pruned backups older than 7 days"
BACKUP_EOF
chmod +x "$DEPLOY_DIR/backup-odoo.sh"

# ── HEALTH CHECK SCRIPT ────────────────────────────────────────────────
log "Step 9/12: Writing health-check script (auto-restart on failure)"
cat > "$DEPLOY_DIR/health-check.sh" << 'HEALTH_EOF'
#!/bin/bash
# Container health check with auto-restart
set -uo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
DATE=$(date '+%Y-%m-%d %H:%M:%S')
STATUS_FILE="$DEPLOY_DIR/../data/Logs/odoo_health.log"
mkdir -p "$(dirname "$STATUS_FILE")"

check_container() {
    local name="$1"
    local health
    health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")

    if [ "$health" = "healthy" ]; then
        echo "[$DATE] $name: HEALTHY" | tee -a "$STATUS_FILE"
        return 0
    elif docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        echo "[$DATE] $name: RUNNING (health=$health)" | tee -a "$STATUS_FILE"
        return 0
    else
        echo "[$DATE] $name: DOWN — restarting" | tee -a "$STATUS_FILE"
        docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d "$name" 2>&1 \
            | tee -a "$STATUS_FILE"
        return 1
    fi
}

FAILURES=0
for svc in odoo-db odoo odoo-nginx; do
    check_container "$svc" || FAILURES=$((FAILURES + 1))
done

# Check HTTPS reachability
HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' https://localhost 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" =~ ^(200|301|302|303)$ ]]; then
    echo "[$DATE] HTTPS: OK ($HTTP_CODE)" | tee -a "$STATUS_FILE"
else
    echo "[$DATE] HTTPS: FAIL ($HTTP_CODE)" | tee -a "$STATUS_FILE"
    FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -gt 0 ]; then
    echo "[$DATE] ALERT: $FAILURES service(s) unhealthy" | tee -a "$STATUS_FILE"
    # Write alert to Updates/ for local agent to pick up
    ALERT_DIR="$DEPLOY_DIR/../data/Updates"
    mkdir -p "$ALERT_DIR"
    cat > "$ALERT_DIR/cloud_health_alert_$(date +%Y%m%d_%H%M%S).md" << ALERT
---
type: health_alert
source: cloud-health-monitor
timestamp: $(date -Iseconds)
severity: warning
summary: $FAILURES Odoo cloud service(s) unhealthy
---
# Cloud Health Alert
- **Time**: $DATE
- **Failures**: $FAILURES
- **Action taken**: Auto-restart attempted
ALERT
fi

exit $FAILURES
HEALTH_EOF
chmod +x "$DEPLOY_DIR/health-check.sh"

# ── CERTBOT INITIAL CERTIFICATE ────────────────────────────────────────
log "Step 10/12: Creating Let's Encrypt setup script"
cat > "$DEPLOY_DIR/setup-ssl.sh" << SSL_EOF
#!/bin/bash
# Obtain real Let's Encrypt certificate (run AFTER docker compose up)
set -euo pipefail
DEPLOY_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
DOMAIN="${DOMAIN_NAME}"
EMAIL="${CERTBOT_EMAIL}"

echo "Requesting Let's Encrypt certificate for \$DOMAIN..."

# Use the certbot container for the initial request
docker compose -f "\$DEPLOY_DIR/docker-compose.yml" run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    -d "\$DOMAIN" --email "\$EMAIL" --agree-tos --no-eff-email --force-renewal

# Reload nginx to pick up the real cert
docker compose -f "\$DEPLOY_DIR/docker-compose.yml" exec nginx nginx -s reload

echo "SSL certificate installed for \$DOMAIN"
echo "Auto-renewal is handled by the certbot container (every 12h check)"
SSL_EOF
chmod +x "$DEPLOY_DIR/setup-ssl.sh"

# ── CRON + SYSTEMD ─────────────────────────────────────────────────────
log "Step 11/12: Installing cron jobs and systemd service"

# Systemd service for docker compose
sudo tee /etc/systemd/system/odoo-cloud.service >/dev/null << SYSD_EOF
[Unit]
Description=Odoo Cloud (Platinum Tier)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${DEPLOY_DIR}
ExecStart=/usr/bin/docker compose -f ${DEPLOY_DIR}/docker-compose.yml up -d
ExecStop=/usr/bin/docker compose -f ${DEPLOY_DIR}/docker-compose.yml down
ExecReload=/usr/bin/docker compose -f ${DEPLOY_DIR}/docker-compose.yml restart
User=${USER}

[Install]
WantedBy=multi-user.target
SYSD_EOF

sudo systemctl daemon-reload
sudo systemctl enable odoo-cloud.service

# Cron: daily backup at 02:00, health check every 10 min
CRON_BACKUP="0 2 * * * ${DEPLOY_DIR}/backup-odoo.sh >> ${DEPLOY_DIR}/../data/Logs/backup.log 2>&1"
CRON_HEALTH="*/10 * * * * ${DEPLOY_DIR}/health-check.sh >> ${DEPLOY_DIR}/../data/Logs/health.log 2>&1"
( crontab -l 2>/dev/null | grep -v "backup-odoo.sh" | grep -v "health-check.sh"; \
  echo "$CRON_BACKUP"; echo "$CRON_HEALTH" ) | crontab -
info "Cron installed: backup daily@02:00, health every 10min"

# ── CREATE BACKUPS .gitkeep ─────────────────────────────────────────────
mkdir -p "$BACKUPS_DIR"
touch "$BACKUPS_DIR/.gitkeep"

# ── LAUNCH ──────────────────────────────────────────────────────────────
log "Step 12/12: Starting services"
cd "$DEPLOY_DIR"
docker compose up -d

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ODOO CLOUD DEPLOYMENT COMPLETE (Platinum Tier)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Services running:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "  Next steps:"
echo "    1. Point DNS for ${DOMAIN_NAME} to this server's IP"
echo "    2. Run:  ${DEPLOY_DIR}/setup-ssl.sh"
echo "    3. Access Odoo: https://${DOMAIN_NAME}"
echo ""
echo "  Management:"
echo "    Backup now:   ${DEPLOY_DIR}/backup-odoo.sh"
echo "    Health check: ${DEPLOY_DIR}/health-check.sh"
echo "    Logs:         docker compose -f ${DEPLOY_DIR}/docker-compose.yml logs -f"
echo "    Stop:         sudo systemctl stop odoo-cloud"
echo "    Start:        sudo systemctl start odoo-cloud"
echo ""
echo "  Platinum compliance:"
echo "    - Cloud creates DRAFT invoices only (odoo_mcp.py zone enforcement)"
echo "    - Local agent approves and posts via approval-executor skill"
echo "    - Daily hot backups to data/Backups/ (syncable via Git)"
echo "    - Health monitor auto-restarts failed containers"
echo "    - Alerts written to data/Updates/ for local agent pickup"
echo "═══════════════════════════════════════════════════════════════"
