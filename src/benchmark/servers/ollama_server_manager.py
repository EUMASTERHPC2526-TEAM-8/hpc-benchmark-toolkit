"""
Ollama-specific server manager implementation.

Handles Ollama server lifecycle:
- Health checks via /api/tags
- Model pulling via /api/pull
"""

from typing import List, Dict, Any
import time
import threading
from benchmark.servers.base_server_manager import BaseServerManager
from benchmark.utility import requests


class OllamaServerManager(BaseServerManager):
    """
    Server manager for Ollama inference service.

    Manages Ollama server health checks and model preparation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ollama server manager.

        Args:
            config: Configuration containing model name and other Ollama settings
        """
        super().__init__(config)
        self.model = config.get("model")
        if not self.model:
            raise ValueError("Ollama configuration must include 'model' parameter")

    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Verify Ollama server health by checking /api/tags endpoint.

        Args:
            endpoints: List of Ollama server URLs (e.g., ["http://node1:11434"])
            timeout: Maximum time in seconds to wait for each endpoint

        Returns:
            True if all endpoints are healthy, False otherwise
        """
        print(f'Checking health of {len(endpoints)} Ollama endpoints with timeout {timeout}s each...')

        for endpoint in endpoints:
            print(f'\nChecking endpoint: {endpoint}')
            start = time.time()
            healthy = False

            while time.time() - start < timeout:
                healthy = self._check_single_endpoint_health(endpoint)
                if healthy:
                    break
                time.sleep(2)

            if not healthy:
                print(f"Timeout reached: Ollama endpoint {endpoint} is not healthy.")
                return False

        print("All Ollama endpoints are healthy.")
        return True

    def _check_single_endpoint_health(self, endpoint: str) -> bool:
        """
        Check health of a single Ollama endpoint.

        Args:
            endpoint: Ollama server URL

        Returns:
            True if healthy, False otherwise
        """
        try:
            print(f"Checking Ollama health at {endpoint}...", flush=True)
            res = requests.get(f"{endpoint}/api/tags", timeout=5)
            status = res.status_code
            data = res.text
            print(f"Health check response from {endpoint}: HTTP {status}, Data: {data}")

            if 200 <= status < 300:
                print(f"Ollama healthy at {endpoint}")
                return True
            else:
                print(f"Ollama unhealthy at {endpoint} (HTTP {status})")
                return False

        except Exception as e:
            print(f"Ollama unreachable at {endpoint}: {e}")
            return False

    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Prepare Ollama service by pulling the model on all endpoints.

        Args:
            endpoints: List of Ollama server URLs
            timeout: Maximum time in seconds for model pulling

        Returns:
            True if model pulled successfully on all endpoints, False otherwise
        """
        threads = []
        results = [False] * len(endpoints)

        for idx, endpoint in enumerate(endpoints):
            print(f"\nPulling model '{self.model}' from {endpoint}...")
            t = threading.Thread(
                target=self._pull_model_on_endpoint,
                args=(endpoint, results, idx, timeout)
            )
            t.start()
            threads.append(t)

        # Wait for all pulls to complete
        for t in threads:
            t.join()

        return all(results)

    def _pull_model_on_endpoint(self, endpoint: str, results: List[bool],
                                idx: int, timeout: int):
        """
        Pull model on a single endpoint.

        Args:
            endpoint: Ollama server URL
            results: Shared list to store success/failure
            idx: Index in results list
            timeout: Request timeout
        """
        try:
            res = requests.post(
                f"{endpoint}/api/pull",
                json={"model": self.model, "stream": False},
                timeout=timeout
            )
            status = res.status_code
            data = res.text

            if 200 <= status < 300:
                print(f"Pulled model '{self.model}' at {endpoint}: {data}")
                results[idx] = True
            else:
                print(f"Failed to pull model '{self.model}' at {endpoint} (HTTP {status})")
                results[idx] = False

        except Exception as e:
            print(f"Error pulling model '{self.model}' at {endpoint}: {e}")
            results[idx] = False

    def get_health_check_endpoint(self) -> str:
        """
        Get Ollama health check endpoint path.

        Returns:
            "/api/tags"
        """
        return "/api/tags"

    @classmethod
    def parse_service_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Ollama-specific configuration from recipe.

        Args:
            recipe_config: Full recipe configuration

        Returns:
            Dict containing:
                - model: Model name to use
                - Any other Ollama-specific settings

        Raises:
            ValueError: If required configuration is missing
        """
        workload = recipe_config.get("workload", {})
        servers = recipe_config.get("servers", {})

        model = workload.get("model")
        if not model:
            raise ValueError("Ollama recipe must specify 'workload.model'")

        config = {
            "model": model,
            "service_config": servers.get("service_config", {})
        }

        return config
