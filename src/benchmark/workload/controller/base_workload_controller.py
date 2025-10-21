"""
Base class for controlling workload execution from the orchestrator side.

This class manages communication with client nodes that execute the actual
benchmark workload. It does NOT run the workload itself - it coordinates
with WorkloadExecutor instances running on client nodes.
"""

from abc import ABC
from typing import List, Dict, Any
import time
from benchmark.utility import requests
import json


class BaseWorkloadController(ABC): # Will be renamed to BaseWorkloadController (workload context)
    """
    Base class for orchestrator-side workload coordination.

    Responsibilities:
    - Verify client nodes are ready
    - Trigger workload execution on client nodes
    - Fetch benchmark results/metrics
    - Stop workload execution

    The actual workload execution happens on client nodes via BaseWorkloadExecutor.
    """

    def __init__(self, client_nodes: List[str], port: int = 5000,
                 timeout: int = 30, health_timeout: int = 120):
        """
        Initialize the workload controller.

        Args:
            client_nodes: List of client node hostnames/IPs
            port: Port where client workload executor servers are running
            timeout: Default timeout for requests in seconds
            health_timeout: Timeout for health checks in seconds
        """
        self.client_nodes = client_nodes
        self.port = port
        self.timeout = timeout
        self.health_timeout = health_timeout

    def verify_client_health(self) -> bool:
        """
        Verify that all client workload executor servers are ready.

        Returns:
            True if all clients are healthy, False otherwise
        """
        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/health"
            print(f"Waiting for client node {node} to be healthy at {url}...")
            start = time.time()
            healthy = False

            while time.time() - start < self.health_timeout:
                try:
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200:
                        print(f"Client node {node} is healthy: {resp.text}")
                        healthy = True
                        break
                except Exception as e:
                    print(f"Client node {node} not healthy yet: {e}")
                time.sleep(2)

            if not healthy:
                print(f"ERROR: Client node {node} did not become healthy in time.")
                return False

        return True

    def start_workload(self, workload_config: Dict[str, Any]) -> bool:
        """
        Trigger workload execution on all client nodes.

        Args:
            workload_config: Configuration for workload execution
                            (server endpoints, model, duration, etc.)

        Returns:
            True if workload started successfully on all clients, False otherwise
        """
        all_success = True

        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/start"
            try:
                print(f"Starting workload on client node {node}: {url}")
                resp = requests.post(url, json=workload_config, timeout=self.timeout)
                data = json.loads(resp.text)

                if resp.status_code == 200 and data.get("success"):
                    print(f"Workload started successfully on {node}.")
                else:
                    print(f"Failed to start workload on {node}: {resp.text}")
                    all_success = False
            except Exception as e:
                print(f"Error starting workload on {node}: {e}")
                all_success = False

        return all_success

    def fetch_metrics(self) -> Dict[str, Any]:
        """
        Fetch benchmark metrics from all client nodes.

        Returns:
            Dictionary mapping node names to their metrics,
            or empty dict if fetching failed
        """
        all_metrics = {}

        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/metrics"
            try:
                print(f"Fetching metrics from client node {node}: {url}")
                resp = requests.get(url, timeout=self.timeout)
                data = json.loads(resp.text)

                if resp.status_code == 200:
                    all_metrics[node] = data
                    print(f"Metrics fetched from {node}.")
                else:
                    print(f"Failed to fetch metrics from {node}: {resp.text}")
                    all_metrics[node] = {"error": resp.text}
            except Exception as e:
                print(f"Error fetching metrics from {node}: {e}")
                all_metrics[node] = {"error": str(e)}

        return all_metrics

    def terminate_workload(self) -> bool:
        """
        Stop workload execution on all client nodes.

        Returns:
            True if workload stopped successfully on all clients, False otherwise
        """
        all_success = True

        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/stop"
            try:
                print(f"Stopping workload on client node {node}: {url}")
                resp = requests.post(url, timeout=self.timeout)
                data = json.loads(resp.text)

                if resp.status_code == 200 and data.get("success"):
                    print(f"Workload stopped successfully on {node}.")
                else:
                    print(f"Failed to stop workload on {node}: {resp.text}")
                    all_success = False
            except Exception as e:
                print(f"Error stopping workload on {node}: {e}")
                all_success = False

        return all_success

    def get_service_name(self) -> str:
        """
        Get the name of the service this controller manages.

        Returns:
            Service name (e.g., "ollama", "postgres")
        """
        return self.__class__.__name__.replace("WorkloadController", "").lower()
