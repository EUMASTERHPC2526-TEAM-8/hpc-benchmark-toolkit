#!/bin/bash

# Script per sincronizzare file monitoring su MeluXina
# Uso: ./sync_to_meluxina.sh [username]

set -e

# Configurazione
MELUXINA_USER="${1:-your_username}"  # Sostituisci con il tuo username
MELUXINA_HOST="meluxina.lxp.lu"
REMOTE_PATH="/project/home/p200776/team8/hpc-benchmark-toolkit"

echo "=========================================="
echo "Sync Monitoring to MeluXina"
echo "=========================================="
echo "User: $MELUXINA_USER"
echo "Host: $MELUXINA_HOST"
echo "Remote path: $REMOTE_PATH"
echo ""

# Verifica che la directory monitoring esista
if [ ! -d "monitoring" ]; then
    echo "Error: monitoring directory not found"
    echo "Please run this script from the repository root"
    exit 1
fi

# Chiedi conferma
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 0
fi

# Crea directory remote se non esiste
echo "[1] Creating remote directories..."
ssh "${MELUXINA_USER}@${MELUXINA_HOST}" "mkdir -p ${REMOTE_PATH}/monitoring/meluxina ${REMOTE_PATH}/monitoring/grafana/provisioning/{datasources,dashboards} ${REMOTE_PATH}/monitoring/grafana/dashboards"

# Sincronizza monitoring
echo ""
echo "[2] Syncing monitoring files..."
rsync -avz --progress \
    --include='monitoring/***' \
    --exclude='*' \
    ./ "${MELUXINA_USER}@${MELUXINA_HOST}:${REMOTE_PATH}/"

# Rendi eseguibili gli script
echo ""
echo "[3] Making scripts executable..."
ssh "${MELUXINA_USER}@${MELUXINA_HOST}" "
cd ${REMOTE_PATH}/monitoring/meluxina
chmod +x *.sh *.py
cd ${REMOTE_PATH}/monitoring
chmod +x start.sh stop.sh
"

# Verifica
echo ""
echo "[4] Verifying sync..."
ssh "${MELUXINA_USER}@${MELUXINA_HOST}" "ls -lh ${REMOTE_PATH}/monitoring/meluxina/"

echo ""
echo "=========================================="
echo "✓ Sync complete!"
echo "=========================================="
echo ""
echo "Next steps on MeluXina:"
echo "  1. ssh ${MELUXINA_USER}@${MELUXINA_HOST}"
echo "  2. cd ${REMOTE_PATH}/monitoring/meluxina"
echo "  3. ./setup_meluxina.sh"
echo ""
