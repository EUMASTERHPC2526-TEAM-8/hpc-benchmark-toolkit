#!/usr/bin/env python3
"""
HPC Benchmark Toolkit CLI

A command-line interface for managing and running HPC benchmark recipes.
"""
import argparse
import os
import sys
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


class BenchmarkCLI:
    """Main CLI class for HPC Benchmark Toolkit"""

    def __init__(self):
        self.recipes_dir = Path(__file__).parent / "src" / "recipes"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)

    def list_recipes(self) -> List[Path]:
        """List all available recipes"""
        return sorted(self.recipes_dir.glob("*.yaml"))

    def display_recipes(self):
        """Display available recipes with details"""
        recipes = self.list_recipes()

        if not recipes:
            print("No recipes found in:", self.recipes_dir)
            return

        print("\nAvailable Recipes:")
        print("=" * 80)

        for idx, recipe_path in enumerate(recipes, 1):
            with open(recipe_path) as f:
                recipe = yaml.safe_load(f)

            scenario = recipe.get("scenario", "N/A")
            service = recipe.get("workload", {}).get("service", "N/A")
            nodes = recipe.get("orchestration", {}).get("total_nodes", "N/A")
            model = recipe.get("workload", {}).get("model", "N/A")

            print(f"\n[{idx}] {recipe_path.name}")
            print(f"    Scenario: {scenario}")
            print(f"    Service:  {service}")
            print(f"    Nodes:    {nodes}")
            print(f"    Model:    {model}")

        print("\n" + "=" * 80)

    def select_recipe(self) -> Optional[Path]:
        """Interactive recipe selection"""
        recipes = self.list_recipes()

        if not recipes:
            print("No recipes found. Please create one first.")
            return None

        self.display_recipes()

        while True:
            try:
                choice = input("\nSelect recipe number (or 'q' to quit): ").strip()
                if choice.lower() == 'q':
                    return None

                idx = int(choice) - 1
                if 0 <= idx < len(recipes):
                    return recipes[idx]
                else:
                    print(f"Please enter a number between 1 and {len(recipes)}")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\nCancelled.")
                return None

    def create_recipe(self):
        """Interactive recipe creation"""
        print("\n" + "=" * 80)
        print("Create New Recipe")
        print("=" * 80)

        # Select service type
        print("\nSelect service type:")
        print("[1] Ollama")
        print("[2] vLLM")
        print("[3] vLLM (Distributed)")

        while True:
            try:
                choice = input("\nEnter choice (1-3): ").strip()
                if choice in ['1', '2', '3']:
                    break
                print("Please enter 1, 2, or 3")
            except KeyboardInterrupt:
                print("\nCancelled.")
                return

        if choice == '1':
            self._create_ollama_recipe()
        elif choice == '2':
            self._create_vllm_recipe(distributed=False)
        else:
            self._create_vllm_recipe(distributed=True)

    def _prompt(self, message: str, default: Any = None, required: bool = True) -> str:
        """Helper for prompting user input"""
        if default is not None:
            prompt = f"{message} [{default}]: "
        else:
            prompt = f"{message}: "

        while True:
            try:
                value = input(prompt).strip()
                if value:
                    return value
                elif default is not None:
                    return str(default)
                elif not required:
                    return ""
                else:
                    print("This field is required.")
            except KeyboardInterrupt:
                print("\nCancelled.")
                sys.exit(0)

    def _prompt_int(self, message: str, default: int) -> int:
        """Helper for prompting integer input"""
        while True:
            value = self._prompt(message, default)
            try:
                return int(value)
            except ValueError:
                print("Please enter a valid number.")

    def _create_ollama_recipe(self):
        """Create Ollama recipe interactively"""
        print("\n--- Ollama Recipe Configuration ---")

        # Basic info
        scenario = self._prompt("Scenario name", "ollama-benchmark")
        partition = self._prompt("Partition", "gpu")
        account = self._prompt("Account", "p200981")
        qos = self._prompt("QoS", "default")

        # Node allocation
        print("\n--- Node Allocation ---")
        server_nodes = self._prompt_int("Number of server nodes", 2)
        client_nodes = self._prompt_int("Number of client nodes", 2)
        monitor_nodes = self._prompt_int("Number of monitor nodes", 1)
        total_nodes = server_nodes + client_nodes + monitor_nodes

        # Resources
        print("\n--- Resources ---")
        server_gpus = self._prompt_int("GPUs per server node", 2)
        server_cpus = self._prompt_int("CPUs per server task", 1)
        server_mem = self._prompt_int("Memory per server (GB)", 32)
        client_gpus = self._prompt_int("GPUs per client node", 1)
        client_cpus = self._prompt_int("CPUs per client task", 2)
        client_mem = self._prompt_int("Memory per client (GB)", 16)

        # Workload
        print("\n--- Workload Configuration ---")
        model = self._prompt("Model name", "llama2")
        clients_per_node = self._prompt_int("Clients per node", 10)
        duration = self._prompt("Duration", "2m")
        warmup = self._prompt("Warmup time", "1m")
        time_limit = self._prompt("Job time limit", "02:00:00")

        # Artifacts
        print("\n--- Artifacts ---")
        containers_dir = self._prompt("Containers directory", "/project/home/p200776/team8/containers/")
        ollama_image = self._prompt("Ollama container filename", "ollama_latest.sif")
        python_image = self._prompt("Python container filename", "python_3_12_3_v2.sif")

        # Binds
        print("\n--- Bind Mounts ---")
        ollama_cache = self._prompt("Ollama cache directory", "/project/home/p200776/team8/.ollama")
        scratch_dir = self._prompt("Scratch directory", "/project/home/p200776/team8/")

        # Build recipe
        recipe = {
            "scenario": scenario,
            "partition": partition,
            "account": account,
            "qos": qos,
            "modules": ["Apptainer"],
            "orchestration": {
                "mode": "slurm",
                "total_nodes": total_nodes,
                "node_allocation": {
                    "servers": {"nodes": server_nodes},
                    "clients": {"nodes": client_nodes},
                    "monitors": {"nodes": monitor_nodes}
                },
                "job_config": {
                    "time_limit": time_limit,
                    "exclusive": True
                }
            },
            "resources": {
                "servers": {
                    "gpus": server_gpus,
                    "cpus_per_task": server_cpus,
                    "mem_gb": server_mem
                },
                "clients": {
                    "gpus": client_gpus,
                    "cpus_per_task": client_cpus,
                    "mem_gb": client_mem
                }
            },
            "workload": {
                "component": "inference",
                "service": "ollama",
                "clients_per_node": clients_per_node,
                "duration": duration,
                "warmup": warmup,
                "model": model
            },
            "servers": {
                "health_check": {
                    "enabled": True,
                    "timeout": 300,
                    "interval": 5,
                    "endpoint": "/api/tags"
                },
                "service_config": {
                    "gpu_layers": 0
                }
            },
            "artifacts": {
                "containers_dir": containers_dir,
                "service": {
                    "path": ollama_image,
                    "remote": "docker://ollama/ollama:latest"
                },
                "python": {
                    "path": python_image,
                    "remote": "docker://python:3.12.3-slim"
                }
            },
            "binds": [
                f"{ollama_cache}:/root/.ollama:rw",
                f"{scratch_dir}:/scratch:rw"
            ]
        }

        # Save recipe
        filename = f"ollama_{scenario.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.yaml"
        filepath = self.recipes_dir / filename

        with open(filepath, 'w') as f:
            yaml.dump(recipe, f, default_flow_style=False, sort_keys=False)

        print(f"\n✓ Recipe created: {filepath}")

    def _create_vllm_recipe(self, distributed: bool = False):
        """Create vLLM recipe interactively"""
        service_name = "vLLM (Distributed)" if distributed else "vLLM"
        print(f"\n--- {service_name} Recipe Configuration ---")

        # Basic info
        scenario = self._prompt("Scenario name", "vllm-distributed-benchmark" if distributed else "vllm-benchmark")
        partition = self._prompt("Partition", "gpu")
        account = self._prompt("Account", "p")
        qos = self._prompt("QoS", "default")

        # Node allocation
        print("\n--- Node Allocation ---")
        server_nodes = self._prompt_int("Number of server nodes", 2 if distributed else 1)
        client_nodes = self._prompt_int("Number of client nodes", 2)
        total_nodes = server_nodes + client_nodes

        # Resources
        print("\n--- Resources ---")
        server_gpus = self._prompt_int("GPUs per server node", 2)
        server_cpus = self._prompt_int("CPUs per server task", 4)
        server_mem = self._prompt_int("Memory per server (GB)", 64)
        client_cpus = self._prompt_int("CPUs per client task", 4)
        client_mem = self._prompt_int("Memory per client (GB)", 16)

        # Workload
        print("\n--- Workload Configuration ---")
        print("Model examples:")
        print("  - facebook/opt-1.3b (small, ~5GB)")
        print("  - meta-llama/Llama-2-7b-hf (medium, ~13GB)")
        print("  - meta-llama/Llama-2-13b-hf (large, ~26GB)")
        model = self._prompt("Model name", "facebook/opt-1.3b")
        clients_per_node = self._prompt_int("Clients per node", 10)
        duration = self._prompt("Duration", "5m")
        warmup = self._prompt("Warmup time", "30s")
        time_limit = self._prompt("Job time limit", "00:30:00")

        # Distributed configuration
        distributed_config = {}
        if distributed:
            print("\n--- Distributed Configuration ---")
            total_gpus = server_nodes * server_gpus
            tensor_parallel = self._prompt_int("Tensor parallel size", total_gpus)
            pipeline_parallel = self._prompt_int("Pipeline parallel size", 1)
            max_model_len = self._prompt_int("Max model length", 2048)
            gpu_memory_util = float(self._prompt("GPU memory utilization (0.0-1.0)", "0.7"))

            distributed_config = {
                "enabled": True,
                "backend": "ray",
                "tensor_parallel_size": tensor_parallel,
                "pipeline_parallel_size": pipeline_parallel,
                "ray": {
                    "dashboard_port": 8265,
                    "object_manager_port": 8076,
                    "node_manager_port": 8077,
                    "num_cpus_per_node": server_cpus,
                    "num_gpus_per_node": server_gpus
                }
            }

        # Artifacts
        print("\n--- Artifacts ---")
        containers_dir = self._prompt("Containers directory", "/project/home/p200776/team8/containers/")
        vllm_image = self._prompt("vLLM container filename", "vllm_0_5_0.sif")
        python_image = self._prompt("Python container filename", "python_3_12_3_v2.sif")

        # Binds
        print("\n--- Bind Mounts ---")
        hf_cache = self._prompt("HuggingFace cache directory", "/project/home/p200776/team8/.cache/huggingface")
        scratch_dir = self._prompt("Scratch directory", "/project/home/p200776/team8/")

        binds = [
            f"{hf_cache}:/root/.cache/huggingface:rw",
            f"{scratch_dir}:/scratch:rw"
        ]

        if distributed:
            ray_tmp = self._prompt("Ray temp directory", "/project/home/p200776/team8/ray_tmp")
            binds.append(f"{ray_tmp}:/tmp/ray:rw")

        # Build recipe
        recipe = {
            "scenario": scenario,
            "partition": partition,
            "account": account,
            "qos": qos,
            "modules": ["Apptainer"],
            "orchestration": {
                "mode": "slurm",
                "total_nodes": total_nodes,
                "node_allocation": {
                    "servers": {"nodes": server_nodes},
                    "clients": {"nodes": client_nodes}
                },
                "job_config": {
                    "time_limit": time_limit,
                    "exclusive": True
                }
            },
            "resources": {
                "servers": {
                    "gpus": server_gpus,
                    "cpus_per_task": server_cpus,
                    "mem_gb": server_mem
                },
                "clients": {
                    "gpus": 0,
                    "cpus_per_task": client_cpus,
                    "mem_gb": client_mem
                }
            },
            "workload": {
                "component": "inference",
                "service": "vllm",
                "clients_per_node": clients_per_node,
                "duration": duration,
                "warmup": warmup,
                "model": model
            },
            "servers": {
                "health_check": {
                    "enabled": True,
                    "timeout": 600,
                    "interval": 5,
                    "endpoint": "/health"
                },
                "service_config": {}
            },
            "artifacts": {
                "containers_dir": containers_dir,
                "service": {
                    "path": vllm_image,
                    "remote": "docker://vllm/vllm-openai:v0.5.0"
                },
                "python": {
                    "path": python_image,
                    "remote": "docker://python:3.12.3-slim"
                }
            },
            "binds": binds
        }

        # Add distributed config if applicable
        if distributed:
            recipe["servers"]["service_config"]["distributed"] = distributed_config
            recipe["servers"]["service_config"]["max_model_len"] = max_model_len
            recipe["servers"]["service_config"]["gpu_memory_utilization"] = gpu_memory_util
            recipe["servers"]["service_config"]["enforce_eager"] = True
            recipe["servers"]["service_config"]["trust_remote_code"] = False

        # Save recipe
        filename = f"vllm_{scenario.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.yaml"
        filepath = self.recipes_dir / filename

        with open(filepath, 'w') as f:
            yaml.dump(recipe, f, default_flow_style=False, sort_keys=False)

        print(f"\n✓ Recipe created: {filepath}")

    def deploy_and_run(self, recipe_path: Optional[Path] = None):
        """Deploy and run a recipe"""
        if recipe_path is None:
            recipe_path = self.select_recipe()
            if recipe_path is None:
                return

        print(f"\n--- Deploy and Run: {recipe_path.name} ---")

        # Load recipe to get scenario name
        with open(recipe_path) as f:
            recipe = yaml.safe_load(f)

        scenario = recipe.get("scenario", "experiment")

        # Get cluster and remote path info
        cluster = self._prompt("Cluster SSH alias (e.g., meluxina)", required=True)
        remote_path = self._prompt("Remote path on cluster", f"/project/home/p200776/team8/{scenario}")

        # Generate sbatch script
        sbatch_file = f"{scenario}_server_only.sh"
        print(f"\n[1] Generating sbatch script...")

        try:
            project_root = Path(__file__).parent
            generator_path = project_root / "src" / "generate_sbatch_simple.py"

            subprocess.run([
                "python3", str(generator_path),
                str(recipe_path), sbatch_file
            ], check=True)
            print(f"    ✓ Generated: {sbatch_file}")
        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed to generate sbatch script: {e}")
            return

        # Copy files to cluster
        print(f"\n[2] Copying files to cluster...")

        try:
            # Resolve local directories relative to this file to avoid cwd issues
            project_root = Path(__file__).parent
            local_benchmark = project_root / "benchmark"
            local_config = project_root / "config"

            # Copy benchmark directory
            subprocess.run([
                "rsync", "-avz", str(local_benchmark), f"{cluster}:{remote_path}/"
            ], check=True)

            # Copy config directory
            subprocess.run([
                "rsync", "-avz", str(local_config), f"{cluster}:{remote_path}/"
            ], check=True)

            # Copy sbatch script and recipe
            subprocess.run([
                "scp", sbatch_file, str(recipe_path), f"{cluster}:{remote_path}/"
            ], check=True)

            print(f"    ✓ Files copied to {cluster}:{remote_path}/")
        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed to copy files: {e}")
            return

        # Create logs directory and submit job
        print(f"\n[3] Submitting job...")

        try:
            # Create logs directory
            subprocess.run([
                "ssh", cluster, f"mkdir -p {remote_path}/logs"
            ], check=True)

            # Submit job
            result = subprocess.run([
                "ssh", cluster, f"cd {remote_path} && sbatch {sbatch_file}"
            ], check=True, capture_output=True, text=True)

            print(f"    ✓ Job submitted!")
            print(f"\n{result.stdout}")

            # Show monitoring command
            print(f"\nMonitor job with:")
            print(f"  ssh {cluster} 'squeue -u $USER'")
            print(f"\nView logs with:")
            print(f"  ssh {cluster} 'tail -f {remote_path}/logs/*.out'")

        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed to submit job: {e}")
            return


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="HPC Benchmark Toolkit CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available recipes
  %(prog)s list

  # Select and deploy a recipe interactively
  %(prog)s run

  # Create a new recipe
  %(prog)s create

  # Deploy a specific recipe
  %(prog)s run --recipe src/recipes/ollama_meluxina.yaml
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    subparsers.add_parser('list', help='List available recipes')

    # Create command
    subparsers.add_parser('create', help='Create a new recipe interactively')

    # Run command
    run_parser = subparsers.add_parser('run', help='Deploy and run a recipe')
    run_parser.add_argument('--recipe', type=str, help='Path to recipe file')

    args = parser.parse_args()

    cli = BenchmarkCLI()

    if args.command == 'list':
        cli.display_recipes()

    elif args.command == 'create':
        cli.create_recipe()

    elif args.command == 'run':
        recipe_path = Path(args.recipe) if args.recipe else None
        cli.deploy_and_run(recipe_path)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
