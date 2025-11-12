#!/bin/bash
#SBATCH --job-name=pushgateway
#SBATCH --qos=default
#SBATCH --partition=gpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4GB
#SBATCH --time=01:00:00
#SBATCH --output=logs/pushgateway_%j.log
#SBATCH --error=logs/pushgateway_%j.err

# Script per avviare Pushgateway su MeluXina
# Uso: sbatch start_pushgateway.sh

set -e

echo "=========================================="
echo "Starting Pushgateway on MeluXina"
echo "=========================================="
echo "Node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "Date: $(date)"
echo ""

# Configurazione
BASE_DIR="$HOME/hpc-monitoring"
PUSHGATEWAY_BINARY="$BASE_DIR/bin/pushgateway"
DATA_DIR="$BASE_DIR/pushgateway_data"
PORT=9091

# Crea directory se non esiste
mkdir -p "$DATA_DIR"

# Scarica il binario se non esiste
if [ ! -f "$PUSHGATEWAY_BINARY" ]; then
    echo "Pushgateway binary not found. Downloading..."
    mkdir -p "$BASE_DIR/bin"
    cd "$BASE_DIR/bin"
    wget -q https://github.com/prometheus/pushgateway/releases/download/v1.6.2/pushgateway-1.6.2.linux-amd64.tar.gz
    tar xzf pushgateway-1.6.2.linux-amd64.tar.gz --strip-components=1
    rm pushgateway-1.6.2.linux-amd64.tar.gz
    chmod +x pushgateway
    echo "✓ Downloaded Pushgateway v1.6.2"
fi

echo "Pushgateway will be accessible at:"
echo "  http://$(hostname):$PORT"
echo ""

# Avvia Pushgateway
cd "$DATA_DIR"
"$PUSHGATEWAY_BINARY" \
    --web.listen-address=":$PORT" \
    --persistence.file=pushgateway.db \
    --persistence.interval=5m \
    --log.level=info

echo ""
echo "Pushgateway stopped."
echo "Job completed at: $(date)"
