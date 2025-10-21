"""
vLLM-specific workload controller implementation.

Manages vLLM client workload execution from the orchestrator side.
Communicates with VllmWorkloadExecutor instances running on client nodes.
"""

from typing import List
from benchmark.workload.controller import BaseWorkloadController


class VllmWorkloadController(BaseWorkloadController):
    """
    Workload controller for vLLM inference benchmarking.

    This class inherits all functionality from BaseWorkloadController
    and can be extended with vLLM-specific methods if needed.

    The base class already provides:
    - verify_client_health()
    - start_workload()
    - fetch_metrics()
    - terminate_workload()
    """

    def __init__(self, client_nodes: List[str], port: int = 5000,
                 timeout: int = 30, health_timeout: int = 120):
        """
        Initialize vLLM workload controller.

        Args:
            client_nodes: List of client node hostnames/IPs
            port: Port where vLLM workload executor servers are running
            timeout: Default timeout for requests in seconds
            health_timeout: Timeout for health checks in seconds
        """
        super().__init__(client_nodes, port, timeout, health_timeout)
        print(f"Initialized vLLM workload controller for {len(client_nodes)} client nodes")

    # The base class provides all necessary functionality.
    # Additional vLLM-specific methods can be added here if needed.
