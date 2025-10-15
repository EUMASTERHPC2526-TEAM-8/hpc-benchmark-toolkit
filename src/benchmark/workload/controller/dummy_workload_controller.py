"""
Dummy workload controller for template/example service.
"""
from benchmark.workload.controller import BaseWorkloadController
from typing import List

class DummyWorkloadController(BaseWorkloadController): # Will be renamed to DummyWorkloadController (workload context)
    def __init__(self, client_nodes: List[str], port: int = 5000, timeout: int = 30, health_timeout: int = 120):
        super().__init__(client_nodes, port, timeout, health_timeout)

    def verify_client_health(self) -> bool:
        print(f"[Dummy] Verifying client health for nodes: {self.client_nodes}")
        return True

    def start_workload(self, workload_config):
        print(f"[Dummy] Starting workload with config: {workload_config}")
        return True
