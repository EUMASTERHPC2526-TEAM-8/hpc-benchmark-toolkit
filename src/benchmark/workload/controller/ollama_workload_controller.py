"""
Ollama-specific workload controller implementation.

Manages Ollama client workload execution from the orchestrator side.
Communicates with OllamaWorkloadExecutor instances running on client nodes.
"""

from typing import List
from benchmark.workload.controller import BaseWorkloadController


class OllamaWorkloadController(BaseWorkloadController): # Will be renamed to OllamaWorkloadController (workload context)
    """
    Workload controller for Ollama inference benchmarking.

    This class inherits all functionality from BaseWorkloadController
    and can be extended with Ollama-specific methods if needed.

    The base class already provides:
    - verify_client_health()
    - start_workload()
    - fetch_metrics()
    - terminate_workload()
    """

    def __init__(self, client_nodes: List[str], port: int = 5000,
                 timeout: int = 30, health_timeout: int = 120):
        """
        Initialize Ollama workload controller.

        Args:
            client_nodes: List of client node hostnames/IPs
            port: Port where Ollama workload executor servers are running
            timeout: Default timeout for requests in seconds
            health_timeout: Timeout for health checks in seconds
        """
        super().__init__(client_nodes, port, timeout, health_timeout)
        print(f"Initialized Ollama workload controller for {len(client_nodes)} client nodes")

    # The base class provides all necessary functionality.
    # Additional Ollama-specific methods can be added here if needed.
