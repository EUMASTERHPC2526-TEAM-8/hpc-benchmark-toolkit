"""
Ray cluster manager for distributed vLLM deployments.

This module handles Ray cluster initialization and management for multi-node
vLLM deployments with tensor/pipeline parallelism.
"""

from typing import Dict, Any, List, Optional
import subprocess
import time
import socket


class RayClusterManager:
    """
    Manages Ray cluster lifecycle for distributed vLLM.

    Handles:
    - Ray head node initialization
    - Worker node connection
    - Health checks
    - Cluster teardown
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ray cluster manager.

        Args:
            config: Ray configuration containing:
                - dashboard_port: Port for Ray dashboard (default: 8265)
                - object_manager_port: Port for object manager (default: 8076)
                - node_manager_port: Port for node manager (default: 8077)
                - num_cpus_per_node: CPUs per node
                - num_gpus_per_node: GPUs per node
        """
        self.config = config
        self.dashboard_port = config.get("dashboard_port", 8265)
        self.object_manager_port = config.get("object_manager_port", 8076)
        self.node_manager_port = config.get("node_manager_port", 8077)
        self.num_cpus = config.get("num_cpus_per_node", 4)
        self.num_gpus = config.get("num_gpus_per_node", 1)
        self.head_address: Optional[str] = None

    def get_local_ip(self) -> str:
        """
        Get the local IP address for Ray cluster communication.

        Returns:
            Local IP address as string
        """
        try:
            # Create a socket to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            print(f"Warning: Could not determine local IP, using localhost: {e}")
            return "127.0.0.1"

    def start_head_node(self, temp_dir: str = "/tmp/ray") -> str:
        """
        Start Ray head node.

        Args:
            temp_dir: Directory for Ray temporary files

        Returns:
            Ray head address (e.g., "192.168.1.100:6379")

        Raises:
            RuntimeError: If head node fails to start
        """
        print("Starting Ray head node...")

        local_ip = self.get_local_ip()

        cmd = [
            "ray", "start",
            "--head",
            f"--node-ip-address={local_ip}",
            f"--dashboard-port={self.dashboard_port}",
            f"--object-manager-port={self.object_manager_port}",
            f"--node-manager-port={self.node_manager_port}",
            f"--num-cpus={self.num_cpus}",
            f"--num-gpus={self.num_gpus}",
            f"--temp-dir={temp_dir}",
            "--block"
        ]

        print(f"Ray head command: {' '.join(cmd)}")

        try:
            # Start Ray head node in background
            # We don't use --block here, instead we check status separately
            cmd_no_block = [c for c in cmd if c != "--block"]
            result = subprocess.run(
                cmd_no_block,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(f"Ray head node failed to start: {result.stderr}")

            # Parse head address from output
            # Ray outputs: "Ray runtime started. Using address: <address>"
            for line in result.stdout.split('\n'):
                if "Ray runtime started" in line or "address:" in line.lower():
                    print(f"Ray head output: {line}")

            # Head address is typically <ip>:6379
            self.head_address = f"{local_ip}:6379"
            print(f"Ray head node started at {self.head_address}")

            # Wait a bit for head node to fully initialize
            time.sleep(5)

            return self.head_address

        except subprocess.TimeoutExpired:
            raise RuntimeError("Ray head node start timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to start Ray head node: {e}")

    def start_worker_node(self, head_address: str, temp_dir: str = "/tmp/ray") -> bool:
        """
        Start Ray worker node and connect to head.

        Args:
            head_address: Address of Ray head node (e.g., "192.168.1.100:6379")
            temp_dir: Directory for Ray temporary files

        Returns:
            True if worker started successfully

        Raises:
            RuntimeError: If worker fails to connect
        """
        print(f"Starting Ray worker node, connecting to {head_address}...")

        local_ip = self.get_local_ip()

        cmd = [
            "ray", "start",
            f"--address={head_address}",
            f"--node-ip-address={local_ip}",
            f"--object-manager-port={self.object_manager_port}",
            f"--node-manager-port={self.node_manager_port}",
            f"--num-cpus={self.num_cpus}",
            f"--num-gpus={self.num_gpus}",
            f"--temp-dir={temp_dir}",
        ]

        print(f"Ray worker command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(f"Ray worker failed to start: {result.stderr}")

            print(f"Ray worker node connected to {head_address}")
            print(result.stdout)

            # Wait for worker to fully connect
            time.sleep(5)

            return True

        except subprocess.TimeoutExpired:
            raise RuntimeError("Ray worker start timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to start Ray worker: {e}")

    def check_cluster_status(self) -> Dict[str, Any]:
        """
        Check Ray cluster status.

        Returns:
            Dict with cluster information:
                - nodes: Number of nodes
                - cpus: Total CPUs
                - gpus: Total GPUs
                - status: "healthy" or "unhealthy"
        """
        try:
            result = subprocess.run(
                ["ray", "status"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return {"status": "unhealthy", "error": result.stderr}

            # Parse Ray status output
            output = result.stdout
            print(f"Ray cluster status:\n{output}")

            # Extract basic info (simplified parsing)
            status_info = {
                "status": "healthy",
                "output": output
            }

            return status_info

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def stop_ray(self) -> bool:
        """
        Stop Ray on this node (head or worker).

        Returns:
            True if stopped successfully
        """
        print("Stopping Ray node...")

        try:
            result = subprocess.run(
                ["ray", "stop", "--force"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("Ray node stopped successfully")
                return True
            else:
                print(f"Ray stop warning: {result.stderr}")
                return True  # Force stop, so we consider it successful

        except Exception as e:
            print(f"Error stopping Ray: {e}")
            return False

    @staticmethod
    def get_ray_start_command(
        role: str,
        head_address: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate Ray start command for bash scripts.

        Args:
            role: "head" or "worker"
            head_address: Ray head address (required for workers)
            config: Ray configuration

        Returns:
            Bash command string to start Ray
        """
        if config is None:
            config = {}

        dashboard_port = config.get("dashboard_port", 8265)
        object_manager_port = config.get("object_manager_port", 8076)
        node_manager_port = config.get("node_manager_port", 8077)
        num_cpus = config.get("num_cpus_per_node", 4)
        num_gpus = config.get("num_gpus_per_node", 1)
        temp_dir = config.get("temp_dir", "/tmp/ray")

        if role == "head":
            cmd = (
                f"ray start --head "
                f"--dashboard-port={dashboard_port} "
                f"--object-manager-port={object_manager_port} "
                f"--node-manager-port={node_manager_port} "
                f"--num-cpus={num_cpus} "
                f"--num-gpus={num_gpus} "
                f"--temp-dir={temp_dir}"
            )
        elif role == "worker":
            if not head_address:
                raise ValueError("head_address required for worker nodes")
            cmd = (
                f"ray start --address={head_address} "
                f"--object-manager-port={object_manager_port} "
                f"--node-manager-port={node_manager_port} "
                f"--num-cpus={num_cpus} "
                f"--num-gpus={num_gpus} "
                f"--temp-dir={temp_dir}"
            )
        else:
            raise ValueError(f"Unknown role: {role}")

        return cmd

    @staticmethod
    def generate_vllm_distributed_command(
        model: str,
        tensor_parallel_size: int,
        pipeline_parallel_size: int = 1,
        host: str = "0.0.0.0",
        port: int = 8000,
        max_model_len: Optional[int] = None,
        gpu_memory_utilization: float = 0.9,
        enforce_eager: bool = False
    ) -> str:
        """
        Generate vLLM server command for distributed deployment.

        Args:
            model: Model name/path
            tensor_parallel_size: Number of GPUs for tensor parallelism
            pipeline_parallel_size: Number of stages for pipeline parallelism
            host: Host to bind server
            port: Port to bind server
            max_model_len: Maximum sequence length
            gpu_memory_utilization: GPU memory utilization fraction
            enforce_eager: Force eager execution

        Returns:
            Command string to start distributed vLLM
        """
        cmd = (
            f"python3 -m vllm.entrypoints.openai.api_server "
            f"--host {host} "
            f"--port {port} "
            f"--model {model} "
            f"--tensor-parallel-size {tensor_parallel_size} "
            f"--pipeline-parallel-size {pipeline_parallel_size} "
            f"--gpu-memory-utilization {gpu_memory_utilization} "
            f"--distributed-executor-backend ray "
        )

        if max_model_len:
            cmd += f"--max-model-len {max_model_len} "

        if enforce_eager:
            cmd += "--enforce-eager "

        return cmd.strip()
