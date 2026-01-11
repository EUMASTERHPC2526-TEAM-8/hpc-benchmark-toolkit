#!/bin/bash -l
#SBATCH --job-name=ollama-meluxina-test
#SBATCH --partition=gpu
#SBATCH --account=p200981
#SBATCH --nodes=5
#SBATCH --ntasks=5
#SBATCH --cpus-per-task=2
#SBATCH --qos=default
#SBATCH --gres=gpu:2
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/ollama-meluxina-test_20260111_141733_%j.out
#SBATCH --error=logs/ollama-meluxina-test_20260111_141733_%j.err

set -e
export OUTPUT_DIR="$(pwd)/experiments/ollama-meluxina-test_20260111_141733"
mkdir -p $OUTPUT_DIR
LOG_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOG_DIR"

# Capture EVERYTHING the sbatch wrapper prints (stdout+stderr) into one file
exec > >(tee -a "$LOG_DIR/job.log") 2>&1

mkdir -p /project/home/p200776/team8/containers/
BENCHMARK_DIR="$(pwd)/benchmark"

# Create bind mount directories if they don't exist
mkdir -p /project/home/p200776/team8/.ollama
mkdir -p /project/home/p200776/team8/

NODES=($(scontrol show hostname $SLURM_NODELIST))
SERVER_NODE_LIST="${NODES[@]:0:2}"
CLIENT_NODE_LIST="${NODES[@]:2:2}"
SERVER_NODES_ARRAY=($SERVER_NODE_LIST)

# For distributed vLLM (Ray-based), orchestrator must run on head node (has GPU)
# For other services, use dedicated orchestrator node
if [[ "ollama" == "vllm" ]]; then
    ORCH_NODE="${SERVER_NODES_ARRAY[0]}"
    echo "Using Ray head node as orchestrator: $ORCH_NODE"
else
    ORCH_NODE="${NODES[-1]}"
fi

module load Apptainer

echo "Experiment ID: ollama-meluxina-test_20260111_141733"
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

for NODE in $SERVER_NODE_LIST; do
    srun --nodes=1 --ntasks=1 --gpus=2 --nodelist=$NODE --cpus-per-task=1 --output=$OUTPUT_DIR/container_${NODE}.log \
        bash -c "apptainer exec --nv --bind /project/home/p200776/team8/.ollama:/root/.ollama:rw --bind /project/home/p200776/team8/:/scratch:rw /project/home/p200776/team8/containers//ollama_latest.sif bash -c 'export OLLAMA_HOST=0.0.0.0:11434; ollama serve;'" &
    pids+=($!)
done

echo "Waiting 5 seconds for service executors to start..."
sleep 5


echo "Starting workload executor servers on $CLIENT_NODE_LIST..."

    # Launch workload executor servers on client nodes
    # These run the general workload_executor entry point and select the correct service implementation
    for NODE in $CLIENT_NODE_LIST; do
        srun --nodes=1 --nodelist=$NODE --ntasks=1 --cpus-per-task=2 --output=$OUTPUT_DIR/client_${NODE}.log \
            bash -c "apptainer exec /project/home/p200776/team8/containers//python_3_12_3_v2.sif bash -c 'pip install flask requests && python3 -m benchmark.workload.workload_executor --service ollama --port 6000'" &
        pids+=($!)
    done

echo "Waiting 5 seconds for workload executor servers to start..."
sleep 5

echo "Starting orchestrator on $ORCH_NODE..."

# For distributed vLLM, only pass the head node to orchestrator
# For other services, pass all server nodes
ORCHESTRATOR_SERVER_NODES="$SERVER_NODE_LIST"

# Launch orchestrator on orchestrator node
# The orchestrator uses the new class-based architecture:
# 1. Creates ServerManager (service-specific) to verify servers and prepare service
# 2. Creates WorkloadController (service-specific) to coordinate client execution
# For vLLM (Ray-based), allocate 1 GPU to orchestrator since it's on head node
if [[ "ollama" == "vllm" ]]; then
    ORCH_GRES="--gres=gpu:1"
else
    ORCH_GRES=""
fi

srun --nodes=1 --nodelist=$ORCH_NODE --ntasks=1 --cpus-per-task=1 $ORCH_GRES --overlap --output=$OUTPUT_DIR/orchestrator.log \
    bash -c "apptainer exec /project/home/p200776/team8/containers//python_3_12_3_v2.sif bash -c \
    'pip install pyyaml requests flask && python3 -m benchmark.orchestrator \
        --server-nodes $ORCHESTRATOR_SERVER_NODES \
        --client-nodes $CLIENT_NODE_LIST \
        --client-port 6000 \
        --server-port 11434 \
        --workload-config-file config/workload_config.json \
        --timeout 600 || echo Orchestrator failed'"
orchestrator_pid=$!
pids+=($!)

echo "Nodes launched, waiting for orchestrator to finish..."

wait $orchestrator_pid
echo "Experiment complete."

