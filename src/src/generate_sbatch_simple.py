#!/usr/bin/env python3
"""
Generate SLURM sbatch script for benchmark execution.

This script generates an sbatch file that:
1. Starts service containers (e.g., Ollama) on server nodes
2. Starts workload executor containers on client nodes
3. Runs the orchestrator to coordinate the benchmark

Uses the new class-based architecture:
- OllamaWorkloadExecutor (runs on client nodes)
- BenchmarkOrchestrator (coordinates the benchmark)
"""
import sys
import yaml
import json
import os
from pathlib import Path
from datetime import datetime
from module_config import get_modules_for_recipe

CLIENT_PORT = 6000  # Default port for client workload executor servers

def load_recipe(recipe_path):
    with open(recipe_path, "r") as f:
        return yaml.safe_load(f)

def generate_distributed_vllm_script(service_image_path, gpu_flag, bind_flags, gpus_per_node, cpus_server, server_launch_cmd):
    ray_temp_dir = "/tmp/ray"
    
    return f"""
# Initialize Ray cluster for distributed vLLM
SERVER_NODES_ARRAY=($SERVER_NODE_LIST)
HEAD_NODE="${{SERVER_NODES_ARRAY[0]}}"
WORKER_NODES="${{SERVER_NODES_ARRAY[@]:1}}"

echo "Ray head node: $HEAD_NODE"
echo "Ray worker nodes: $WORKER_NODES"

# Define local Ray temp directory on host to avoid network filesystem issues with sockets
HOST_RAY_TMP="/tmp/ray_$SLURM_JOB_ID"
echo "Using host-local Ray temp dir: $HOST_RAY_TMP"

# Stop any existing Ray processes and clean stale state
echo "Stopping any existing Ray processes and cleaning stale state..."
for NODE in $SERVER_NODE_LIST; do
    srun --nodes=1 --ntasks=1 --nodelist=$NODE bash -c "apptainer exec {service_image_path} ray stop --force 2>/dev/null || true"
    srun --nodes=1 --ntasks=1 --nodelist=$NODE bash -c "rm -rf $HOST_RAY_TMP; mkdir -p $HOST_RAY_TMP"
done
sleep 5

# Create helper script for Ray head
cat > $OUTPUT_DIR/start_ray_head.sh << 'RAYHEADSCRIPT'
#!/bin/bash
HEAD_IP=$(hostname -I | awk '{{print $1}}')
echo "Ray head IP: $HEAD_IP"
ray start --head \\
    --node-ip-address=$HEAD_IP \\
    --port=6379 \\
    --object-manager-port=8076 \\
    --node-manager-port=8077 \\
    --num-gpus={gpus_per_node} \\
    --num-cpus={cpus_server} \\
    --temp-dir={ray_temp_dir} \\
    --disable-usage-stats
sleep infinity
RAYHEADSCRIPT
chmod +x $OUTPUT_DIR/start_ray_head.sh

# Start Ray head node
echo "Starting Ray head node on $HEAD_NODE..."
srun --nodes=1 --ntasks=1 --gpus={gpus_per_node} --nodelist=$HEAD_NODE --cpus-per-task={cpus_server} --output=$OUTPUT_DIR/ray_head.log \\
    apptainer exec {gpu_flag} {bind_flags} --bind $HOST_RAY_TMP:{ray_temp_dir} {service_image_path} bash $OUTPUT_DIR/start_ray_head.sh &
RAY_HEAD_PID=$!
pids+=($RAY_HEAD_PID)

echo "Waiting for Ray head to initialize..."
sleep 20

# Use head node hostname directly - Ray will resolve it
HEAD_ADDRESS="${{HEAD_NODE}}:6379"
echo "Ray head address: $HEAD_ADDRESS"

# Create helper script for Ray workers
cat > $OUTPUT_DIR/start_ray_worker.sh << 'RAYWORKERSCRIPT'
#!/bin/bash
WORKER_IP=$(hostname -I | awk '{{print $1}}')
echo "Ray worker IP: $WORKER_IP"
ray start \\
    --address=$1 \\
    --node-ip-address=$WORKER_IP \\
    --object-manager-port=8076 \\
    --node-manager-port=8077 \\
    --num-gpus={gpus_per_node} \\
    --num-cpus={cpus_server} \\
    --temp-dir={ray_temp_dir} \\
    --disable-usage-stats
sleep infinity
RAYWORKERSCRIPT
chmod +x $OUTPUT_DIR/start_ray_worker.sh

# Start Ray workers on remaining nodes
WORKER_PIDS=()
for NODE in $WORKER_NODES; do
    echo "Starting Ray worker on $NODE..."
    srun --nodes=1 --ntasks=1 --gpus={gpus_per_node} --nodelist=$NODE --cpus-per-task={cpus_server} --output=$OUTPUT_DIR/ray_worker_${{NODE}}.log \\
        apptainer exec {gpu_flag} {bind_flags} --bind $HOST_RAY_TMP:{ray_temp_dir} {service_image_path} bash $OUTPUT_DIR/start_ray_worker.sh $HEAD_ADDRESS &
    WORKER_PIDS+=($!)
    pids+=($!)
done

echo "Waiting for Ray workers to connect..."
sleep 30
echo "Ray cluster should be ready!"

# Create helper script for vLLM
cat > $OUTPUT_DIR/start_vllm.sh << 'VLLMSCRIPT'
#!/bin/bash
export RAY_ADDRESS=$1
{server_launch_cmd}
VLLMSCRIPT
chmod +x $OUTPUT_DIR/start_vllm.sh

# Start distributed vLLM on head node only (Ray will distribute across cluster)
echo "Starting distributed vLLM server on Ray head node..."
echo "Using RAY_ADDRESS: $HEAD_ADDRESS"
# Use srun with --overlap to run on the head node alongside Ray
srun --nodes=1 --ntasks=1 --nodelist=$HEAD_NODE --cpus-per-task=1 --overlap --output=$OUTPUT_DIR/vllm_server.log --error=$OUTPUT_DIR/vllm_server.log \\
    apptainer exec {gpu_flag} {bind_flags} --bind $HOST_RAY_TMP:{ray_temp_dir} {service_image_path} bash $OUTPUT_DIR/start_vllm.sh $HEAD_ADDRESS &
VLLM_PID=$!
pids+=($VLLM_PID)

echo "Waiting 30 seconds for distributed vLLM to start..."
sleep 30

# Verify vLLM server is responding
echo "Verifying distributed vLLM server health..."
VLLM_READY=false
for i in {{1..10}}; do
    if curl -s -f http://$HEAD_NODE:8080/health >/dev/null 2>&1; then
        echo "Distributed vLLM server is ready and healthy!"
        VLLM_READY=true
        break
    else
        echo "vLLM not ready yet, attempt $i/10. Waiting 10 seconds..."
        sleep 10
    fi
done

if [ "$VLLM_READY" = false ]; then
    echo "ERROR: Distributed vLLM server failed to start properly"
    echo "Check vLLM server logs at: $OUTPUT_DIR/vllm_server.log"
    echo "Last 50 lines of vLLM log:"
    tail -50 $OUTPUT_DIR/vllm_server.log
    exit 1
fi
"""

def generate_standard_service_script(service_image_path, gpu_flag, bind_flags, gpus_per_node, cpus_server, server_launch_cmd):
    return f"""
for NODE in $SERVER_NODE_LIST; do
    srun --nodes=1 --ntasks=1 --gpus={gpus_per_node} --nodelist=$NODE --cpus-per-task={cpus_server} --output=$OUTPUT_DIR/container_${{NODE}}.log \\
        bash -c "apptainer exec {gpu_flag} {bind_flags} {service_image_path} bash -c '{server_launch_cmd}'" &
    pids+=($!)
done

echo "Waiting 5 seconds for service executors to start..."
sleep 5
"""

def generate_sbatch(recipe, output_path):
    scenario = recipe.get("scenario", "experiment")
    server_nodes = int(recipe["orchestration"]["node_allocation"]["servers"]["nodes"])
    client_nodes = int(recipe["orchestration"]["node_allocation"]["clients"]["nodes"])
    orchestrator_nodes = 1
    total_nodes = server_nodes + orchestrator_nodes + client_nodes
    container_dir = recipe["artifacts"]["containers_dir"]
    service_image = recipe["artifacts"]["service"]
    python_image = recipe["artifacts"]["python"]
    
    model = recipe["workload"].get("model", "")
    service_type = recipe["workload"].get("service", "ollama")
    clients_per_node = int(recipe["workload"].get("clients_per_node", 1))
    duration = recipe["workload"].get("duration", "10m")

    cpus_server = recipe["resources"]["servers"].get("cpus_per_task", 1)
    cpus_clients = recipe["resources"]["clients"].get("cpus_per_task", 1)
    mem = recipe["resources"]["servers"].get("mem_gb", 4)
    partition = recipe["partition"]
    account = recipe["account"]
    time_limit = recipe.get("orchestration", {}).get("job_config", {}).get("time_limit", "02:00:00")
    experiment_id = f"{scenario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = f"experiments/{experiment_id}"
    modules_to_load = get_modules_for_recipe(recipe)
    modules_str = "\n".join([f"module load {m}" for m in modules_to_load]) if modules_to_load else ""

    service_image_path = f"{container_dir}/{service_image['path']}"
    python_image_path = f"{container_dir}/{python_image['path']}"

    # Check if this is distributed vLLM
    is_distributed_vllm = False
    distributed_config = {}
    if service_type == "vllm":
        distributed_config = recipe.get("servers", {}).get("service_config", {}).get("distributed", {})
        is_distributed_vllm = distributed_config.get("enabled", False)

    # Service-specific server ports and launch commands
    service_configs = {
        "ollama": {
            "port": 11434,
            "launch_cmd": "export OLLAMA_HOST=0.0.0.0:11434; ollama serve;",
            "use_gpu": True
        },
        "postgres": {
            "port": 5432,
            "launch_cmd": "docker-entrypoint.sh postgres",
            "use_gpu": False
        },
        "vllm": {
            "port": 8080,
            "launch_cmd": f"python3 -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 8080 --model {model}",
            "use_gpu": True
        },
        "vectordb": {
            "port": 19530,
            "launch_cmd": "milvus run standalone",
            "use_gpu": False
        }
    }

    workload_config = {
        "model": model,
        "duration": duration,
        "clients_per_node": clients_per_node,
        "service": service_type
    }
    config_path = "config/workload_config.json"
    config_dir = os.path.dirname(config_path)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(workload_config, f)

    service_config = service_configs.get(service_type, {
        "port": 8000,
        "launch_cmd": "echo 'Unknown service type'",
        "use_gpu": False
    })

    server_port = service_config["port"]
    server_launch_cmd = service_config["launch_cmd"]
    gpu_flag = "--nv" if service_config["use_gpu"] else ""

    # Process bind mounts from recipe
    binds = recipe.get("binds", [])

    # For distributed vLLM, we must use a local /tmp/ray for sockets.
    # Filter out any user-provided binds to /tmp/ray to avoid conflicts/network FS issues.
    if is_distributed_vllm:
        binds = [b for b in binds if ":/tmp/ray" not in b]

    bind_flags = " ".join([f"--bind {bind}" for bind in binds]) if binds else ""

    # Pre-calculate mkdir commands for binds
    if binds:
        bind_mkdir_cmd = "\n".join([f'mkdir -p {bind.split(":")[0]}' for bind in binds])
    else:
        bind_mkdir_cmd = "# No bind mounts configured"

    # Generate distributed vLLM specific configuration
    if is_distributed_vllm:
        tensor_parallel = distributed_config.get("tensor_parallel_size", 1)
        pipeline_parallel = distributed_config.get("pipeline_parallel_size", 1)
        max_model_len = recipe.get("servers", {}).get("service_config", {}).get("max_model_len", 2048)
        gpu_memory_util = recipe.get("servers", {}).get("service_config", {}).get("gpu_memory_utilization", 0.9)

        # Build distributed vLLM command
        vllm_distributed_cmd = (
            f"python3 -m vllm.entrypoints.openai.api_server "
            f"--host 0.0.0.0 --port {service_config['port']} "
            f"--model {model} "
            f"--tensor-parallel-size {tensor_parallel} "
            f"--pipeline-parallel-size {pipeline_parallel} "
            f"--distributed-executor-backend ray "
            f"--max-model-len {max_model_len} "
            f"--gpu-memory-utilization {gpu_memory_util}"
        )

        service_configs["vllm"]["launch_cmd"] = vllm_distributed_cmd
        server_launch_cmd = vllm_distributed_cmd

    gpus_per_node = recipe["resources"]["servers"]["gpus"]

    # Generate server launch script based on whether it's distributed vLLM or not
    if is_distributed_vllm:
        server_launch_script = generate_distributed_vllm_script(
            service_image_path, gpu_flag, bind_flags, gpus_per_node, cpus_server, server_launch_cmd
        )
    else:
        server_launch_script = generate_standard_service_script(
            service_image_path, gpu_flag, bind_flags, gpus_per_node, cpus_server, server_launch_cmd
        )

    # Only pull service image if location file does not exist
    check_service_image = f"""
if [ ! -f "{service_image_path}" ]; then
    echo "Service container not found at {service_image_path}, pulling from {service_image["remote"]}..."
    apptainer pull {service_image_path} {service_image["remote"]}
fi
"""

    # Only pull Python image if location file does not exist
    check_python_image = f"""
if [ ! -f "{python_image_path}" ]; then
    echo "Python container not found at {python_image_path}, pulling from {python_image["remote"]}..."
    apptainer pull {python_image_path} {python_image["remote"]}
fi
"""

    # Pre-calculate the orchestrator server nodes environment variable
    if is_distributed_vllm:
        orch_server_nodes_env = 'ORCHESTRATOR_SERVER_NODES="${SERVER_NODES_ARRAY[0]}"'
    else:
        orch_server_nodes_env = 'ORCHESTRATOR_SERVER_NODES="$SERVER_NODE_LIST"'

    script = f"""#!/bin/bash -l
#SBATCH --job-name={scenario}
#SBATCH --partition={partition}
#SBATCH --account={account}
#SBATCH --nodes={total_nodes}
#SBATCH --ntasks={total_nodes}
#SBATCH --cpus-per-task={max(cpus_server, cpus_clients)}
#SBATCH --qos=default
#SBATCH --gres=gpu:{recipe["resources"]["servers"]["gpus"]}
#SBATCH --mem={mem}G
#SBATCH --time={time_limit}
#SBATCH --output=logs/{experiment_id}_%j.out
#SBATCH --error=logs/{experiment_id}_%j.err

set -e
export OUTPUT_DIR="$(pwd)/{output_dir}"
mkdir -p $OUTPUT_DIR
mkdir -p {container_dir}
BENCHMARK_DIR="$(pwd)/benchmark"

# Create bind mount directories if they don't exist
{bind_mkdir_cmd}

NODES=($(scontrol show hostname $SLURM_NODELIST))
SERVER_NODE_LIST="${{NODES[@]:0:{server_nodes}}}"
CLIENT_NODE_LIST="${{NODES[@]:{server_nodes}:{client_nodes}}}"
ORCH_NODE="${{NODES[-1]}}"

{modules_str}

echo "Experiment ID: {experiment_id}"
echo "Server nodes: $SERVER_NODE_LIST"
echo "Client nodes: $CLIENT_NODE_LIST"
echo "Orchestrator node: $ORCH_NODE"

{check_service_image}
{check_python_image}

echo "Starting {service_type} services on $SERVER_NODE_LIST..."

# Launch service containers on server nodes
{server_launch_script}

echo "Starting workload executor servers on $CLIENT_NODE_LIST..."

    # Launch workload executor servers on client nodes
    # These run the general workload_executor entry point and select the correct service implementation
    for NODE in $CLIENT_NODE_LIST; do
        srun --nodes=1 --nodelist=$NODE --ntasks=1 --cpus-per-task={cpus_clients} --output=$OUTPUT_DIR/client_${{NODE}}.log \\
            bash -c "apptainer exec {python_image_path} bash -c 'pip install flask requests && python3 -m benchmark.workload.workload_executor --service {service_type} --port {CLIENT_PORT}'" &
        pids+=($!)
    done

echo "Waiting 5 seconds for workload executor servers to start..."
sleep 5

echo "Starting orchestrator on $ORCH_NODE..."

# For distributed vLLM, only pass the head node to orchestrator
# For other services, pass all server nodes
{orch_server_nodes_env}

# Launch orchestrator on orchestrator node
# The orchestrator uses the new class-based architecture:
# 1. Creates ServerManager (service-specific) to verify servers and prepare service
# 2. Creates WorkloadController (service-specific) to coordinate client execution
srun --nodes=1 --nodelist=$ORCH_NODE --ntasks=1 --cpus-per-task=1 --output=$OUTPUT_DIR/orchestrator.log \\
    bash -c "apptainer exec {python_image_path} bash -c \\
    'pip install pyyaml requests flask && python3 -m benchmark.orchestrator \\
        --server-nodes $ORCHESTRATOR_SERVER_NODES \\
        --client-nodes $CLIENT_NODE_LIST \\
        --client-port {CLIENT_PORT} \\
        --server-port {server_port} \\
        --workload-config-file {config_path} \\
        --timeout 600 || echo Orchestrator failed'"
orchestrator_pid=$!
pids+=($!)

echo "Nodes launched, waiting for orchestrator to finish..."

wait $orchestrator_pid
echo "Experiment complete."

"""
    with open(output_path, "w") as f:
        f.write(script)
    print(f"✓ Generated sbatch script: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_sbatch_simple.py <recipe.yaml> <output.sh>")
        sys.exit(1)
    recipe = load_recipe(sys.argv[1])
    generate_sbatch(recipe, sys.argv[2])
