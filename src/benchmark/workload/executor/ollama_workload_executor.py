"""
Ollama-specific workload executor implementation.

Runs as a Flask server on client nodes and executes Ollama inference workload.
"""

import argparse
from typing import Dict, Any
import threading
from benchmark.workload.executor import BaseWorkloadExecutor


class OllamaWorkloadExecutor(BaseWorkloadExecutor): # Will be renamed to OllamaWorkloadExecutor (workload context)
    """
    Workload executor for Ollama inference benchmarking.

    Runs on client nodes and executes inference requests against
    Ollama servers, collecting performance metrics.
    """

    def __init__(self, port: int = 5000):
        """
        Initialize Ollama workload executor.

        Args:
            port: Port to run the Flask server on
        """
        super().__init__(port)
        print(f"Initialized Ollama workload executor on port {port}")
        # Import here to ensure datasets is installed first
        self._ensure_datasets_installed()

    def _run_benchmark(self, workload_config: Dict[str, Any]):
        """
        Execute Ollama inference benchmark workload.

        Args:
            workload_config: Configuration containing:
                - server_endpoints: List of Ollama server URLs
                - model: Model name
                - duration: How long to run
                - Additional parameters (prompts, concurrency, etc.)
        """
        from datasets import load_dataset
        from benchmark.utility import requests
        import time

        # Parse configuration
        server_endpoints = workload_config.get("server_endpoints", [])
        model = workload_config.get("model")
        duration = workload_config.get("duration", "10m")

        if not server_endpoints:
            raise ValueError("No server_endpoints provided in workload config")
        if not model:
            raise ValueError("No model specified in workload config")

        print(f"Starting Ollama benchmark: model={model}, "
              f"servers={len(server_endpoints)}, duration={duration}", flush=True)

        # Load dataset for prompts
        import random
        print("Loading hellaswag dataset for prompts...", flush=True)
        ds = load_dataset("hellaswag", split="validation")
        num_prompts = len(ds)
        print(f"Loaded {num_prompts} prompts from hellaswag.", flush=True)

        # Function to get a random prompt
        def get_random_prompt():
            idx = random.randint(0, num_prompts - 1)
            return ds[idx]["ctx_a"]

        print("Using random prompts for each request.", flush=True)
        # Initialize metrics
        request_count = 0
        error_count = 0
        total_latency = 0.0
        start_time = time.time()

        # Parse duration (simplified - assumes format like "10m", "2h", "300s")
        duration_seconds = self._parse_duration(duration)
        end_time = start_time + duration_seconds

        print(f"Running benchmark for {duration_seconds} seconds...")

        # Simple round-robin load generation with random prompts
        server_idx = 0
        while self.workload_running and time.time() < end_time:
            endpoint = server_endpoints[server_idx % len(server_endpoints)]
            server_idx += 1

            prompt = get_random_prompt()

            try:
                request_start = time.time()

                # Send inference request to Ollama
                print(f"[{threading.current_thread().name}] Sending request to {endpoint}...", flush=True)
                res = requests.post(
                    f"{endpoint}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=120
                )

                request_latency = time.time() - request_start

                if 200 <= res.status_code < 300:
                    request_count += 1
                    total_latency += request_latency
                else:
                    error_count += 1
                    print(f"Request failed: HTTP {res.status_code}")

            except Exception as e:
                error_count += 1
                print(f"Request error: {e}")

            # Small delay to avoid overwhelming servers
            time.sleep(0.1)

        # Calculate metrics
        elapsed_time = time.time() - start_time
        avg_latency = total_latency / request_count if request_count > 0 else 0
        throughput = request_count / elapsed_time if elapsed_time > 0 else 0

        # Store metrics
        self.metrics = {
            "total_requests": request_count,
            "errors": error_count,
            "elapsed_seconds": elapsed_time,
            "avg_latency_seconds": avg_latency,
            "throughput_rps": throughput,
            "model": model,
            "server_count": len(server_endpoints)
        }

        print(f"Benchmark complete: {request_count} requests, "
              f"{error_count} errors, {throughput:.2f} req/s", flush=True)

    def _ensure_datasets_installed(self):
        """Ensure the datasets package is installed."""
        print("Checking if 'datasets' package is installed...", flush=True)
        import importlib.util
        import subprocess
        import sys

        if importlib.util.find_spec("datasets") is None:
            print("Installing 'datasets' package...", flush=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
        else:
            print("'datasets' package is already installed.", flush=True)

    def _parse_duration(self, duration: str) -> int:
        """
        Parse duration string to seconds.

        Args:
            duration: Duration string (e.g., "10m", "2h", "300s")

        Returns:
            Duration in seconds
        """
        duration = duration.strip()
        if duration.endswith('s'):
            return int(duration[:-1])
        elif duration.endswith('m'):
            return int(duration[:-1]) * 60
        elif duration.endswith('h'):
            return int(duration[:-1]) * 3600
        else:
            # Default to treating as seconds
            return int(duration)


def main():
    """Entry point for running the Ollama workload executor as a standalone server."""
    parser = argparse.ArgumentParser(description="Ollama Workload Executor")
    parser.add_argument("--port", type=int, default=5000,
                       help="Port to run the workload executor server on")
    args = parser.parse_args()

    executor = OllamaWorkloadExecutor(port=args.port)
    executor.run()


if __name__ == "__main__":
    main()
