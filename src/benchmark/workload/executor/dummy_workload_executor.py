"""
Dummy workload executor for template/example service.
"""
from benchmark.workload.executor import BaseWorkloadExecutor
from typing import Dict, Any
import time
import random

class DummyWorkloadExecutor(BaseWorkloadExecutor):
    def __init__(self, port: int = 5000):
        super().__init__(port)

    def _prepare_shared_resources(self, workload_config: Dict[str, Any]):
        """Prepare shared resources (none for dummy executor)."""
        pass

    def _run_benchmark(self, workload_config: Dict[str, Any], thread_id: int) -> Dict[str, Any]:
        """
        Simulate a benchmark workload with dummy requests.
        
        Args:
            workload_config: Configuration with duration and other parameters
            thread_id: ID of this worker thread
            
        Returns:
            Dict with metrics for this thread
        """
        duration = workload_config.get("duration", "10m")
        duration_seconds = self._parse_duration(duration)
        
        print(f"[Dummy Thread {thread_id}] Running for {duration_seconds} seconds", flush=True)
        
        # Initialize thread-local metrics tracking
        request_count = 0
        error_count = 0
        total_latency = 0.0
        latencies = []
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # Initialize per-thread metrics
        with self.metrics_lock:
            self.per_thread_metrics[thread_id] = {
                "requests": 0,
                "errors": 0,
                "total_latency": 0.0,
                "elapsed": 0.0,
                "latencies": []
            }
        
        # Simulate requests
        while self.workload_running and time.time() < end_time:
            try:
                # Simulate request latency (50-200ms)
                latency = random.uniform(0.05, 0.2)
                time.sleep(latency)
                
                request_count += 1
                total_latency += latency
                latencies.append(latency)
                
                # Update per-thread metrics every request
                with self.metrics_lock:
                    self.per_thread_metrics[thread_id] = {
                        "requests": request_count,
                        "errors": error_count,
                        "total_latency": total_latency,
                        "elapsed": time.time() - start_time,
                        "latencies": latencies.copy()
                    }
                    
            except Exception as e:
                error_count += 1
                print(f"[Dummy Thread {thread_id}] Error: {e}", flush=True)
        
        elapsed_time = time.time() - start_time
        print(f"[Dummy Thread {thread_id}] Complete: {request_count} requests, {error_count} errors", flush=True)
        
        return {
            "thread_id": thread_id,
            "total_requests": request_count,
            "errors": error_count,
            "elapsed_seconds": elapsed_time,
            "total_latency": total_latency,
            "latencies": latencies,
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dummy Workload Executor")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    executor = DummyWorkloadExecutor(port=args.port)
    executor.run()
