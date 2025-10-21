"""
Ollama-specific workload executor implementation.

Runs as a Flask server on client nodes and executes Ollama inference workload.
"""

import argparse
import random
import time
from typing import Dict, Any
from benchmark.workload.executor import BaseWorkloadExecutor


class OllamaWorkloadExecutor(BaseWorkloadExecutor):
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

    def _prepare_shared_resources(self, workload_config: Dict[str, Any]):
        """
        Load the dataset once before spawning threads.

        This avoids loading the same dataset multiple times (once per thread).
        """
        print("Loading hellaswag dataset once for all threads...", flush=True)
        from datasets import load_dataset

        ds = load_dataset("hellaswag", split="validation")
        self.shared_resources["dataset"] = ds
        self.shared_resources["num_prompts"] = len(ds)
        print(f"Dataset loaded with {len(ds)} prompts", flush=True)

    def _run_benchmark(self, workload_config: Dict[str, Any], thread_id: int) -> Dict[str, Any]:
        """
        Execute Ollama inference benchmark workload for a single thread.

        Args:
            workload_config: Configuration containing:
                - server_endpoints: List of Ollama server URLs
                - model: Model name
                - duration: How long to run
                - Additional parameters (prompts, concurrency, etc.)
            thread_id: ID of this worker thread

        Returns:
            Dict containing metrics for this thread
        """
        from benchmark.utility import requests

        # Parse configuration
        server_endpoints = workload_config.get("server_endpoints", [])
        model = workload_config.get("model")
        duration = workload_config.get("duration", "10m")

        if not server_endpoints:
            raise ValueError("No server_endpoints provided in workload config")
        if not model:
            raise ValueError("No model specified in workload config")

        # Use shared dataset
        ds = self.shared_resources.get("dataset")
        num_prompts = self.shared_resources.get("num_prompts", 0)

        if not ds or num_prompts == 0:
            raise ValueError("Dataset not loaded in shared resources")

        # Function to get a random prompt
        def get_random_prompt():
            idx = random.randint(0, num_prompts - 1)
            return ds[idx]["ctx_a"]

        # Initialize thread-local metrics
        request_count = 0
        error_count = 0
        total_latency = 0.0
        start_time = time.time()

        # Parse duration (simplified - assumes format like "10m", "2h", "300s")
        duration_seconds = self._parse_duration(duration)
        end_time = start_time + duration_seconds

        print(f"[Thread {thread_id}] Running benchmark for {duration_seconds} seconds...", flush=True)

        # Simple round-robin load generation with random prompts
        # Offset server_idx by thread_id to distribute load
        server_idx = thread_id
        while self.workload_running and time.time() < end_time:
            endpoint = server_endpoints[server_idx % len(server_endpoints)]
            server_idx += 1

            prompt = get_random_prompt()

            try:
                request_start = time.time()

                # Send inference request to Ollama
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
                    print(f"[Thread {thread_id}] Request failed: HTTP {res.status_code}")

            except Exception as e:
                error_count += 1
                print(f"[Thread {thread_id}] Request error: {e}")

            # Small delay to avoid overwhelming servers
            time.sleep(0.1)

        # Calculate thread-local metrics
        elapsed_time = time.time() - start_time

        print(f"[Thread {thread_id}] Benchmark complete: {request_count} requests, "
              f"{error_count} errors", flush=True)

        # Return thread-local metrics (will be aggregated by base class)
        return {
            "thread_id": thread_id,
            "total_requests": request_count,
            "errors": error_count,
            "elapsed_seconds": elapsed_time,
            "total_latency": total_latency,  # This will be summed for avg calculation
        }

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
