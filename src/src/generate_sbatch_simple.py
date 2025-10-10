#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path
from datetime import datetime
from module_config import get_modules_for_recipe

CLIENT_PORT = 6000  # Default port for client servers

def load_recipe(recipe_path):
    with open(recipe_path, "r") as f:
        return yaml.safe_load(f)

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
    cpus = recipe["resources"]["servers"].get("cpus_per_task", 1)
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

    script = f"""#!/bin/bash -l
#SBATCH --job-name={scenario}
#SBATCH --partition={partition}
#SBATCH --account={account}
#SBATCH --nodes={total_nodes}
#SBATCH --ntasks={total_nodes}
#SBATCH --cpus-per-task={cpus}
#SBATCH --qos=default
#SBATCH --mem={mem}G
#SBATCH --time={time_limit}
#SBATCH --output=logs/{experiment_id}_%j.out
#SBATCH --error=logs/{experiment_id}_%j.err

set -e
export OUTPUT_DIR="$(pwd)/{output_dir}"
mkdir -p $OUTPUT_DIR
mkdir -p {container_dir}
BENCHMARK_DIR="$(pwd)/benchmark"

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

echo "Starting services on $SERVER_NODE_LIST..."

# Launch Ollama containers on server nodes
for NODE in $SERVER_NODE_LIST; do
    srun --nodes=1 --nodelist=$NODE --cpus-per-task={cpus} --output=$OUTPUT_DIR/container_${{NODE}}.log \\
        bash -c "apptainer exec --nv {service_image_path} bash -c 'export OLLAMA_HOST=0.0.0.0:11434; ollama serve & sleep 5;'" &
    pids+=($!)
done

echo "Starting clients on $CLIENT_NODE_LIST..."

# Launch Python containers on client nodes (if any)
for NODE in $CLIENT_NODE_LIST; do
    srun --nodes=1 --nodelist=$NODE --ntasks=1 --cpus-per-task={cpus} --output=$OUTPUT_DIR/client_${{NODE}}.log \\
        bash -c "apptainer exec {python_image_path} bash -c 'pip install flask && python3 -m benchmark.clients.ollama_client --port {CLIENT_PORT}'" &
    pids+=($!)
done

echo "Waiting 5 seconds for client nodes to start..."
sleep 5

echo "Starting orchestrator on $ORCH_NODE..."

# Launch orchestrator health check on orchestrator node
srun --nodes=1 --nodelist=$ORCH_NODE --ntasks=1 --cpus-per-task=1 --output=$OUTPUT_DIR/orchestrator.log \
    bash -c "apptainer exec {python_image_path} bash -c 'python3 -m benchmark.orchestrator --server-nodes $SERVER_NODE_LIST --client-nodes $CLIENT_NODE_LIST --client-port {CLIENT_PORT} --model {model} --timeout 600 || echo 'Orchestrator failed''"
orchestrator_pid=$!
pids+=($!)

echo "Nodes launched, waiting for orchestrator to finish..."

wait
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