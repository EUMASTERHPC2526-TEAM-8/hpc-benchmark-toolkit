#!/usr/bin/env python3
"""
Enhanced simplified SLURM script generator - starts server containers with setup.
- Copies Python modules to experiment directory
- Pulls container if missing
- Handles model caching

Usage:
    python generate_sbatch_simple_v2.py recipe.yaml
    python generate_sbatch_simple_v2.py recipe.yaml --output submit.sh
"""

import argparse
import sys
from pathlib import Path
from typing import Dict
from datetime import datetime

import yaml
from module_config import get_modules_for_recipe, generate_module_load_commands


class EnhancedSimpleSlurmGenerator:
    """Generates enhanced SLURM scripts with setup phases."""

    def __init__(self, recipe: Dict, recipe_path: Path):
        self.recipe = recipe
        self.recipe_path = recipe_path
        self.experiment_id = self._generate_experiment_id()

    def _generate_experiment_id(self) -> str:
        """Generate unique experiment ID."""
        scenario = self.recipe.get("scenario", "experiment")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{scenario}_{timestamp}"

    def generate_script(self) -> str:
        """Generate enhanced sbatch script with setup."""

        # Extract configuration
        partition = self.recipe["partition"]
        account = self.recipe["account"]
        qos = self.recipe.get("qos", "")
        scenario = self.recipe["scenario"]
        
        # Get modules to load
        service = self.recipe["workload"]["service"]
        modules = get_modules_for_recipe(self.recipe, service=service)
        module_commands = generate_module_load_commands(modules)

        # Server configuration
        server_nodes = self.recipe["orchestration"]["node_allocation"]["servers"]["nodes"]
        server_res = self.recipe["resources"]["servers"]
        server_gpus = server_res.get("gpus", 0)
        server_cpus = server_res.get("cpus_per_task", 1)
        server_mem = server_res.get("mem_gb", 1)

        # Workload configuration
        workload = self.recipe["workload"]
        service = workload["service"]
        model = workload.get("model", "")
        # Escape single quotes for safe single-quoted shell literals
        model_escaped = model.replace("'", "'\\''")
        exp_id_escaped = self.experiment_id.replace("'", "'\\''")

        # Container and binds
        container = self.recipe["artifacts"]["container"]
        binds = self.recipe.get("binds", [])

        # Service-specific configuration
        service_config = self.recipe.get("servers", {}).get("service_config", {})

        # Build service config arguments
        service_args = []
        if model:
            service_args.append(f"--model '{model}'")

        if service == "vllm":
            tensor_parallel = service_config.get("tensor_parallel_size", 1)
            gpu_mem_util = service_config.get("gpu_memory_utilization", 0.9)
            max_model_len = service_config.get("max_model_len")
            dtype = service_config.get("dtype", "auto")
            trust_remote_code = service_config.get("trust_remote_code", True)

            service_args.append(f"--tensor-parallel-size {tensor_parallel}")
            service_args.append(f"--gpu-memory-utilization {gpu_mem_util}")
            if max_model_len:
                service_args.append(f"--max-model-len {max_model_len}")
            service_args.append(f"--dtype {dtype}")
            if trust_remote_code:
                service_args.append("--trust-remote-code")

        elif service == "ollama":
            gpu_layers = service_config.get("gpu_layers", -1)
            service_args.append(f"--gpu-layers {gpu_layers}")

        service_args_str = " \\\n             ".join(service_args)

        # Build bind mount string with OUTPUT_DIR
        bind_mounts = []
        for bind in binds:
            bind_mounts.append(f"--bind {bind}")
        # Add output dir bind
        bind_mounts.append("--bind $OUTPUT_DIR:/workspace:rw")
        bind_str = " \\\n         ".join(bind_mounts)
        
        # Create bash array string for directory creation
        binds_array = []
        for bind in binds:
            binds_array.append(f'"{bind}"')
        binds_str = " ".join(binds_array)
        
        # Create module loading command for srun
        module_load_cmd = " && ".join([f"module load {module}" for module in modules])

        # Get time limit
        time_limit = "02:00:00"
        if "orchestration" in self.recipe and "job_config" in self.recipe["orchestration"]:
            time_limit = self.recipe["orchestration"]["job_config"].get("time_limit", time_limit)

        # Build the script
        script = f"""#!/bin/bash -l
#SBATCH --job-name={scenario}-server
#SBATCH --partition={partition}
#SBATCH --account={account}"""

        if qos:
            script += f"\n#SBATCH --qos={qos}"

        script += f"""
#SBATCH --nodes={server_nodes}
#SBATCH --ntasks={server_nodes}
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task={server_cpus}
#SBATCH --mem={server_mem}G"""

        if server_gpus > 0:
            script += f"""
#SBATCH --gres=gpu:{server_gpus}"""

        script += f"""
#SBATCH --time={time_limit}
#SBATCH --output=logs/{self.experiment_id}_%j.out
#SBATCH --error=logs/{self.experiment_id}_%j.err

################################################################################
# Enhanced Simplified Server Startup Script
#
# Experiment: {scenario}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Recipe: {self.recipe_path}
#
# Features:
# - Automatic container pull if missing
# - Copies Python benchmark modules
# - Model caching setup
# - Endpoint information logging
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration (export so child processes / containers inherit them)
export EXPERIMENT_ID='{exp_id_escaped}'
export RECIPE_PATH="{self.recipe_path.absolute()}"
export CONTAINER='{container}'
export SERVICE='{service}'
export SERVER_NODES={server_nodes}
export MODEL='{model_escaped}'

echo "========================================================================"
echo "ENHANCED SERVER STARTUP"
echo "========================================================================"
echo "Experiment ID: $EXPERIMENT_ID"
echo "Service:       $SERVICE"
echo "Server Nodes:  $SERVER_NODES"
echo "Job ID:        $SLURM_JOB_ID"
echo "Model:         $MODEL"
echo "Container:     $CONTAINER"
echo "========================================================================"

# Create output directory
OUTPUT_DIR="./experiments/${{EXPERIMENT_ID}}"
mkdir -p $OUTPUT_DIR/logs
mkdir -p $OUTPUT_DIR/benchmark
export OUTPUT_DIR

################################################################################
# Phase 1: Load Python Module and Setup
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 1: Loading Python module and copying benchmark modules"
echo "========================================================================"

# Load HPC modules using configuration
{module_commands}

# Copy benchmark Python modules to experiment directory
SCRIPT_DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"
if [ -d "$SCRIPT_DIR/benchmark" ]; then
    cp -r "$SCRIPT_DIR/benchmark" "$OUTPUT_DIR/"
    echo "✓ Copied benchmark modules to $OUTPUT_DIR/benchmark"

    # Create __init__.py files to ensure it's a package
    touch "$OUTPUT_DIR/benchmark/__init__.py"
    touch "$OUTPUT_DIR/benchmark/servers/__init__.py"
else
    echo "⚠ Warning: benchmark directory not found at $SCRIPT_DIR/benchmark"
    echo "  Creating minimal structure..."
    mkdir -p "$OUTPUT_DIR/benchmark/servers"
    touch "$OUTPUT_DIR/benchmark/__init__.py"
    touch "$OUTPUT_DIR/benchmark/servers/__init__.py"
fi

################################################################################
# Phase 2: Container Setup
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 2: Container verification and pull"
echo "========================================================================"

# Check if container exists
if [ ! -f "$CONTAINER" ]; then
    echo "⚠ Container not found at: $CONTAINER"
    echo ""
    echo "Attempting to pull container..."

    # Create container directory if it doesn't exist
    CONTAINER_DIR=$(dirname "$CONTAINER")
    mkdir -p "$CONTAINER_DIR"

    # Determine container source based on service
    if [ "$SERVICE" = "vllm" ]; then
        CONTAINER_SOURCE="docker://vllm/vllm-openai:latest"
    elif [ "$SERVICE" = "ollama" ]; then
        CONTAINER_SOURCE="docker://ollama/ollama:latest"
    else
        echo "✗ Unknown service: $SERVICE"
        echo "  Please manually create container at: $CONTAINER"
        exit 1
    fi

    echo "Pulling from: $CONTAINER_SOURCE"
    echo "This may take 10-30 minutes depending on image size and network..."

    # Pull container
    if command -v apptainer &> /dev/null; then
        apptainer pull "$CONTAINER" "$CONTAINER_SOURCE" || {{
            echo "✗ Failed to pull container with apptainer"
            exit 1
        }}
    elif command -v singularity &> /dev/null; then
        singularity pull "$CONTAINER" "$CONTAINER_SOURCE" || {{
            echo "✗ Failed to pull container with singularity"
            exit 1
        }}
    else
        echo "✗ Neither apptainer nor singularity found"
        exit 1
    fi

    echo "✓ Container pulled successfully"
else
    echo "✓ Container found: $CONTAINER"
fi

################################################################################
# Phase 3: Create Bind Mount Directories
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 3: Creating bind mount directories"
echo "========================================================================"

# Create all bind mount directories to prevent container failures
echo "Creating bind mount directories..."
for bind in {binds_str}; do
    if [[ "$bind" == *":"* ]]; then
        # Extract host path (before the first colon)
        host_path=$(echo "$bind" | cut -d: -f1)
        echo "Creating directory: $host_path"
        mkdir -p "$host_path"
        echo "✓ Created: $host_path"
    fi
done

echo "✓ All bind mount directories created"

################################################################################
# Phase 4: Model Caching Setup
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 4: Model caching setup"
echo "========================================================================"

# Service-specific model caching setup
if [ "$SERVICE" = "vllm" ]; then
    # HuggingFace cache for vLLM
    export HF_HOME="${{HF_HOME:-$HOME/.cache/huggingface}}"
    export TRANSFORMERS_CACHE="${{TRANSFORMERS_CACHE:-$HF_HOME/hub}}"
    export HF_HUB_OFFLINE="${{HF_HUB_OFFLINE:-0}}"

    echo "Service: vLLM"
    echo "HuggingFace home: $HF_HOME"
    echo "Transformers cache: $TRANSFORMERS_CACHE"

    mkdir -p "$HF_HOME"
    mkdir -p "$TRANSFORMERS_CACHE"

    if [ -n "$MODEL" ] && [[ "$MODEL" == *"/"* ]]; then
        echo "Model: $MODEL"
        MODEL_CACHE_NAME=$(echo "$MODEL" | sed 's#/#--#g')
        MODEL_CACHE_DIR="$TRANSFORMERS_CACHE/models--$MODEL_CACHE_NAME"

        if [ -d "$MODEL_CACHE_DIR" ]; then
            echo "✓ Model found in cache"
        else
            echo "⚠ Model will be downloaded on first startup (5-60 min)"
        fi
    fi

elif [ "$SERVICE" = "ollama" ]; then
    # Ollama model cache
    export OLLAMA_MODELS="${{OLLAMA_MODELS:-$HOME/.ollama/models}}"

    echo "Service: Ollama"
    echo "Ollama models: $OLLAMA_MODELS"

    mkdir -p "$OLLAMA_MODELS"

    echo "Model: $MODEL"
    echo "Note: Model will be pulled automatically inside the container"
    echo "      This happens after server startup and may take 5-60 minutes"

else
    echo "Service: $SERVICE (no specific caching configured)"
fi

################################################################################
# Phase 5: Node Allocation
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 5: Node allocation"
echo "========================================================================"

# Parse node list
NODES=$(scontrol show hostname $SLURM_NODELIST)
echo "Allocated nodes:"
echo "$NODES"
echo ""

# Create node list array
NODES_ARRAY=($NODES)

# Display node assignment
for i in ${{!NODES_ARRAY[@]}}; do
    NODE=${{NODES_ARRAY[$i]}}
    echo "Server $i: $NODE"
done

echo "========================================================================"

################################################################################
# Phase 6: Server Startup
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 6: Launching server container(s)"
echo "========================================================================"

# Set environment variables for container
export CUDA_VISIBLE_DEVICES="${{CUDA_VISIBLE_DEVICES:-0}}"

echo "Starting $SERVICE server(s)..."
echo ""

# Service-specific environment and command
if [ "$SERVICE" = "ollama" ]; then
    # Create a simple launcher script that starts Ollama in container
    cat > $OUTPUT_DIR/launch_ollama_container.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting Ollama server in container..."
ollama serve &
OLLAMA_PID=$!
echo "Started ollama (PID: $OLLAMA_PID)"

# Wait for Ollama to initialize
sleep 10

echo "Pulling model: {model}"
if [ -n "{model}" ]; then
    if ! ollama pull "{model}"; then
        echo "⚠ ollama pull failed or model may already be present"
    fi
else
    echo "⚠ No model specified, skipping pull"
fi

echo "Ollama is ready - keeping container alive"
# Keep the container running
wait $OLLAMA_PID

EOF

    chmod +x $OUTPUT_DIR/launch_ollama_container.sh

    # Start Ollama container in background
    srun --nodes=$SERVER_NODES \\
         --ntasks=$SERVER_NODES \\
         --ntasks-per-node=1 \\
         --cpus-per-task={server_cpus} \\
         --output=$OUTPUT_DIR/logs/ollama_container_%N_%t.log \\
         --label \\
         bash -c "apptainer exec --nv \\
             --env OLLAMA_MODELS=${{OLLAMA_MODELS:-$HOME/.ollama/models}} \\
             --env PATH=\$PATH \\
             {bind_str} \\
             $CONTAINER \\
             sh /workspace/launch_ollama_container.sh" &
    
    CONTAINER_PID=$!
    echo "✓ Ollama container started (PID: $CONTAINER_PID)"
    
    # Wait for Ollama to be ready and list models using host Python
    echo ""
    echo "Waiting for Ollama API to be ready..."
    sleep 15
    
    # Get the node where container is running
    NODE_NAME=$(scontrol show hostname $SLURM_NODELIST | head -n1)
    echo "Checking Ollama on node: $NODE_NAME"
    
    # Use the copied ollama_server.py module to check health and list models
    export PYTHONPATH="$OUTPUT_DIR:$PYTHONPATH"
    if python3 -m benchmark.servers.ollama_server --check-only --port 11434; then
        echo "✓ Ollama health check completed successfully"
    else
        echo "✗ Ollama health check failed"
    fi

    echo ""
    echo "========================================================================"
    echo "Ollama container is running and ready"
    echo "To stop the container: scancel $SLURM_JOB_ID"
    echo "========================================================================"
else
    # vLLM and other services use HuggingFace cache
    srun --nodes=$SERVER_NODES \\
         --ntasks=$SERVER_NODES \\
         --ntasks-per-node=1 \\
         --cpus-per-task={server_cpus} \\
         --output=$OUTPUT_DIR/logs/server_%N_%t.log \\
         --label \\
         bash -c "{module_load_cmd} && export PATH=\$PATH && apptainer exec --nv \\
             --env PYTHONPATH=/workspace:/workspace/benchmark \\
             --env HF_HOME=${{HF_HOME:-$HOME/.cache/huggingface}} \\
             --env TRANSFORMERS_CACHE=${{TRANSFORMERS_CACHE:-$HF_HOME/hub}} \\
             --env PATH=\$PATH \\
             {bind_str} \\
             $CONTAINER \\
             python3 -m benchmark.servers.{service}_server \\
                 --experiment-id $EXPERIMENT_ID \\
                 --output-dir /workspace \\
                 --log-endpoints \\
                 {service_args_str}" &
fi

SERVER_PID=$CONTAINER_PID

echo "✓ Container process started (PID: $SERVER_PID)"

################################################################################
# Phase 7: Container Status Check
################################################################################

echo ""
echo "========================================================================"
echo "PHASE 7: Container status and cleanup"
echo "========================================================================"
echo ""
echo "Container status check complete."
echo "The job will now terminate. The container setup was successful."
echo ""
echo "To run a longer job, modify the script or submit again."
echo "========================================================================"

# Terminate the container after successful setup
echo "Terminating Ollama container..."
if kill $CONTAINER_PID 2>/dev/null; then
    echo "✓ Container terminated gracefully"
else
    echo "⚠ Container may have already exited"
fi

echo ""
echo "========================================================================"
echo "Job completed successfully"
echo "========================================================================"

exit 0
"""

        return script

    def write_script(self, output_path: Path):
        """Write sbatch script to file."""
        script = self.generate_script()

        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write script
        with open(output_path, 'w') as f:
            f.write(script)

        # Make executable
        output_path.chmod(0o755)

        print(f"✓ Enhanced sbatch script generated: {output_path}")


def load_recipe(recipe_path: Path) -> Dict:
    """Load and parse recipe file."""
    if not recipe_path.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")

    with open(recipe_path, 'r') as f:
        recipe = yaml.safe_load(f)

    return recipe


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate enhanced SLURM script (servers only) with automatic setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate script
  %(prog)s recipe.yaml

  # Generate with custom output
  %(prog)s recipe.yaml --output my_submit.sh

  # Validate first
  %(prog)s recipe.yaml --validate

Features:
  - Automatic container pull if missing
  - Copies Python benchmark modules to experiment directory
  - Sets up model caching
  - Logs detailed endpoint information
        """
    )

    parser.add_argument(
        "recipe",
        type=Path,
        help="Recipe file"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output path for sbatch script (default: {scenario}_server_only.sh)"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate recipe before generating"
    )

    args = parser.parse_args()

    try:
        # Validate if requested
        if args.validate:
            print("Validating recipe...")
            from validate_recipe import validate_single_recipe

            is_valid = validate_single_recipe(
                args.recipe,
                interactive=True,
                color=True,
                verbose=True
            )

            if not is_valid:
                print("\n✗ Recipe validation failed")
                sys.exit(1)

            print("\n✓ Recipe validated\n")

        # Load recipe
        recipe = load_recipe(args.recipe)

        # Generate script
        generator = EnhancedSimpleSlurmGenerator(recipe, args.recipe)

        # Determine output path
        if args.output:
            output_path = args.output
        else:
            scenario = recipe.get("scenario", "experiment")
            output_path = Path(f"{scenario}_server_only.sh")

        # Write script
        generator.write_script(output_path)

        print(f"\n✓ Script includes automatic setup:")
        print(f"  - Container pull (if missing)")
        print(f"  - Python modules copy")
        print(f"  - Model caching")
        print(f"  - Endpoint logging")
        print(f"\nTo submit: sbatch {output_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
