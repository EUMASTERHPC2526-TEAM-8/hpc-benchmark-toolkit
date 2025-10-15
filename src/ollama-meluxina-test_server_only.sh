#!/bin/bash -l
#SBATCH --job-name=ollama-meluxina-test
#SBATCH --partition=gpu
#SBATCH --account=p200776
#SBATCH --nodes=3
#SBATCH --ntasks=3
#SBATCH --cpus-per-task=2
#SBATCH --qos=default
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/ollama-meluxina-test_20251011_174217_%j.out
#SBATCH --error=logs/ollama-meluxina-test_20251011_174217_%j.err

set -e
export OUTPUT_DIR="$(pwd)/experiments/ollama-meluxina-test_20251011_174217"
mkdir -p $OUTPUT_DIR
mkdir -p /project/home/p200776/team8/containers/
BENCHMARK_DIR="$(pwd)/benchmark"

NODES=($(scontrol show hostname $SLURM_NODELIST))
SERVER_NODE_LIST="${NODES[@]:0:1}"
CLIENT_NODE_LIST="${NODES[@]:1:1}"
ORCH_NODE="${NODES[-1]}"

module load Apptainer

echo "Experiment ID: ollama-meluxina-test_20251011_174217"
echo "Server nodes: $SERVER_NODE_LIST"
echo "Client nodes: $CLIENT_NODE_LIST"
echo "Orchestrator node: $ORCH_NODE"


if [ ! -f "/project/home/p200776/team8/containers//ollama_latest.sif" ]; then
    echo "Service container not found at /project/home/p200776/team8/containers//ollama_latest.sif, pulling from docker://ollama/ollama:latest..."
    apptainer pull /project/home/p200776/team8/containers//ollama_latest.sif docker://ollama/ollama:latest
fi


if [ ! -f "/project/home/p200776/team8/containers//python_3_12_3_v2.sif" ]; then
    echo "Python container not found at /project/home/p200776/team8/containers//python_3_12_3_v2.sif, pulling from docker://python:3.12.3-slim..."
    apptainer pull /project/home/p200776/team8/containers//python_3_12_3_v2.sif docker://python:3.12.3-slim
fi


echo "Starting ollama services on $SERVER_NODE_LIST..."

# Launch service containers on server nodes
# Service-specific command and port are determined by the service type
for NODE in $SERVER_NODE_LIST; do
    srun --nodes=1 --ntasks=1 --gpus=1 --nodelist=$NODE --cpus-per-task=1 --output=$OUTPUT_DIR/container_${NODE}.log \
        bash -c "apptainer exec --nv /project/home/p200776/team8/containers//ollama_latest.sif bash -c 'export OLLAMA_HOST=0.0.0.0:11434; ollama serve;'" &
    pids+=($!)
done

echo "Waiting 5 seconds for service executors to start..."
sleep 5

echo "Starting workload executor servers on $CLIENT_NODE_LIST..."

    # Launch workload executor servers on client nodes
    # These run the general workload_executor entry point and select the correct service implementation
    for NODE in $CLIENT_NODE_LIST; do
        srun --nodes=1 --nodelist=$NODE --ntasks=1 --cpus-per-task=2 --output=$OUTPUT_DIR/client_${NODE}.log             bash -c "apptainer exec /project/home/p200776/team8/containers//python_3_12_3_v2.sif bash -c 'pip install flask && python3 -m benchmark.workload.workload_executor --service ollama --port 6000'" &
        pids+=($!)
    done

echo "Waiting 5 seconds for workload executor servers to start..."
sleep 5

echo "Starting orchestrator on $ORCH_NODE..."

# Launch orchestrator on orchestrator node
# The orchestrator uses the new class-based architecture:
# 1. Creates ServerManager (service-specific) to verify servers and prepare service
# 2. Creates WorkloadController (service-specific) to coordinate client execution
srun --nodes=1 --nodelist=$ORCH_NODE --ntasks=1 --cpus-per-task=1 --output=$OUTPUT_DIR/orchestrator.log \
    bash -c "apptainer exec /project/home/p200776/team8/containers//python_3_12_3_v2.sif bash -c \
    'python3 -m benchmark.orchestrator \
        --server-nodes $SERVER_NODE_LIST \
        --client-nodes $CLIENT_NODE_LIST \
        --client-port 6000 \
        --server-port 11434 \
        --workload-config-file config/workload_config.json \
        --timeout 600 || echo Orchestrator failed'"
orchestrator_pid=$!
pids+=($!)

echo "Nodes launched, waiting for orchestrator to finish..."

wait orchestrator_pid
echo "Experiment complete."

