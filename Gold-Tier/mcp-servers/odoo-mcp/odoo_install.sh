#!/usr/bin/env bash
# ─── Odoo Community 19+ Local Installation (Docker) ───
# AI Employee Vault — Gold Tier
#
# Prerequisites: Docker installed and running
# Usage: bash odoo_install.sh

set -euo pipefail

ODOO_VERSION="19.0"
ODOO_CONTAINER="odoo"
ODOO_PORT="8069"
PG_CONTAINER="odoo-db"
PG_PASSWORD="odoo"
ODOO_DB="ai_employee"

echo "=== Odoo Community ${ODOO_VERSION} — Docker Setup ==="

# ── Step 1: Pull images ──
echo "[1/5] Pulling Docker images..."
docker pull postgres:16
docker pull odoo:${ODOO_VERSION}

# ── Step 2: Start PostgreSQL ──
echo "[2/5] Starting PostgreSQL container..."
if docker ps -a --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
    echo "  PostgreSQL container already exists, starting..."
    docker start ${PG_CONTAINER} 2>/dev/null || true
else
    docker run -d \
        --name ${PG_CONTAINER} \
        -e POSTGRES_USER=odoo \
        -e POSTGRES_PASSWORD=${PG_PASSWORD} \
        -e POSTGRES_DB=postgres \
        -v odoo-db-data:/var/lib/postgresql/data \
        postgres:16
fi

# Wait for PostgreSQL to be ready
echo "  Waiting for PostgreSQL..."
sleep 5

# ── Step 3: Start Odoo ──
echo "[3/5] Starting Odoo container..."
if docker ps -a --format '{{.Names}}' | grep -q "^${ODOO_CONTAINER}$"; then
    echo "  Odoo container already exists, starting..."
    docker start ${ODOO_CONTAINER} 2>/dev/null || true
else
    docker run -d \
        --name ${ODOO_CONTAINER} \
        --link ${PG_CONTAINER}:db \
        -p ${ODOO_PORT}:8069 \
        -v odoo-data:/var/lib/odoo \
        -v odoo-addons:/mnt/extra-addons \
        -e HOST=db \
        -e USER=odoo \
        -e PASSWORD=${PG_PASSWORD} \
        odoo:${ODOO_VERSION}
fi

echo "  Waiting for Odoo to start..."
sleep 10

# ── Step 4: Verify Odoo is running ──
echo "[4/5] Verifying Odoo is accessible..."
MAX_WAIT=30
WAITED=0
until curl -sf http://localhost:${ODOO_PORT}/web/login > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "  ERROR: Odoo did not start within ${MAX_WAIT}s"
        echo "  Check: docker logs ${ODOO_CONTAINER}"
        exit 1
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo "  Waiting... (${WAITED}s)"
done
echo "  Odoo is running at http://localhost:${ODOO_PORT}"

# ── Step 5: Create database via XML-RPC ──
echo "[5/5] Creating database '${ODOO_DB}'..."
python3 -c "
import xmlrpc.client
try:
    db_proxy = xmlrpc.client.ServerProxy('http://localhost:${ODOO_PORT}/xmlrpc/2/db')
    existing = db_proxy.list()
    if '${ODOO_DB}' in existing:
        print('  Database already exists, skipping creation.')
    else:
        db_proxy.create_database('admin', '${ODOO_DB}', False, 'en_US', 'admin')
        print('  Database created successfully.')
except Exception as e:
    print(f'  Note: Auto-creation skipped ({e})')
    print('  → Open http://localhost:${ODOO_PORT} and create database manually:')
    print('    Master Password: admin')
    print('    Database Name: ${ODOO_DB}')
    print('    Email: admin')
    print('    Password: admin')
" 2>/dev/null || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Odoo URL:     http://localhost:${ODOO_PORT}"
echo "Database:     ${ODOO_DB}"
echo "Admin Login:  admin / admin"
echo "XML-RPC:      http://localhost:${ODOO_PORT}/xmlrpc/2/object"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:${ODOO_PORT} in your browser"
echo "  2. Install 'Invoicing' and 'Accounting' modules"
echo "  3. Set ODOO_DRY_RUN=false in .env when ready"
echo "  4. Test: python mcp-servers/odoo-mcp/odoo_mcp.py --test"
echo ""
echo "Docker commands:"
echo "  Stop:    docker stop ${ODOO_CONTAINER} ${PG_CONTAINER}"
echo "  Start:   docker start ${PG_CONTAINER} && docker start ${ODOO_CONTAINER}"
echo "  Logs:    docker logs ${ODOO_CONTAINER}"
echo "  Remove:  docker rm -f ${ODOO_CONTAINER} ${PG_CONTAINER}"
