#!/bin/bash
set -e

RECIPE="$1"
CLUSTER="$2"
REMOTE_PATH="$3"

SCENARIO=$(python3 -c "import yaml; print(yaml.safe_load(open('$RECIPE'))['scenario'])")
SBATCH_FILE="${SCENARIO}_server_only.sh"

echo "[1] Generating sbatch script..."
python3 src/generate_sbatch_simple.py "$RECIPE" "$SBATCH_FILE"

echo "[2] Copying files to cluster..."
rsync -avz benchmark "$CLUSTER:$REMOTE_PATH/"
rsync -avz config "$CLUSTER:$REMOTE_PATH/"
scp "$SBATCH_FILE" "$RECIPE" "$CLUSTER:$REMOTE_PATH/"

echo "[3] Submitting job..."
ssh "$CLUSTER" mkdir -p "$REMOTE_PATH/logs"
ssh "$CLUSTER" "cd $REMOTE_PATH && sbatch $SBATCH_FILE"

echo "Done. Monitor with: ssh $CLUSTER 'squeue -u $USER'"