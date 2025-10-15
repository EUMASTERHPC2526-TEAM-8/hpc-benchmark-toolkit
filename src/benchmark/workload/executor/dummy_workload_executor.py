"""
Dummy workload executor for template/example service.
"""
from benchmark.workload.executor import BaseWorkloadExecutor
from typing import Dict, Any

class DummyWorkloadExecutor(BaseWorkloadExecutor): # Will be renamed to DummyWorkloadExecutor (workload context)
    def __init__(self, port: int = 5000):
        super().__init__(port)

    def _run_benchmark(self, workload_config: Dict[str, Any]):
        print(f"[Dummy] Running benchmark with config: {workload_config}")
        return {"status": "success", "details": "Dummy benchmark executed."}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dummy Workload Executor")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    executor = DummyWorkloadExecutor(port=args.port)
    executor.run()
