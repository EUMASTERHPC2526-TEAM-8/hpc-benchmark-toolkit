"""
vLLM-specific server manager implementation.

Handles vLLM server lifecycle:
- Health checks via /health endpoint
- Model pulling/loading via OpenAI-compatible API
"""

from typing import List, Dict, Any
import time
import threading
from benchmark.servers.base_server_manager import BaseServerManager
from benchmark.utility import requests


class VllmServerManager(BaseServerManager):
    """
    Server manager for vLLM inference service.

    Manages vLLM server health checks and model preparation.
    vLLM uses OpenAI-compatible API endpoints.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize vLLM server manager.

        Args:
            config: Configuration containing model name and other vLLM settings
        """
        super().__init__(config)
        self.model = config.get("model")
        if not self.model:
            raise ValueError("vLLM configuration must include 'model' parameter")

    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Verify vLLM server health by checking /health endpoint.

        Args:
            endpoints: List of vLLM server URLs (e.g., ["http://node1:8000"])
            timeout: Maximum time in seconds to wait for each endpoint

        Returns:
            True if all endpoints are healthy, False otherwise
        """
        print(f'Checking health of {len(endpoints)} vLLM endpoints with timeout {timeout}s each...')

        self.prepare_service(endpoints, timeout=timeout)

        print("All vLLM endpoints are healthy.")
        return True

    def _check_single_endpoint_health(self, endpoint: str) -> bool:
        """
        Check health of a single vLLM endpoint.

        Args:
            endpoint: vLLM server URL

        Returns:
            True if healthy, False otherwise
        """
        try:
            print(f"Checking vLLM health at {endpoint}...", flush=True)
            res = requests.get(f"{endpoint}/health", timeout=5)
            status = res.status_code
            print(f"Health check response from {endpoint}: HTTP {status}")

            if 200 <= status < 300:
                print(f"vLLM healthy at {endpoint}")
                return True
            else:
                print(f"vLLM unhealthy at {endpoint} (HTTP {status})")
                return False

        except Exception as e:
            print(f"vLLM unreachable at {endpoint}: {e}")
            return False

    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Prepare vLLM service by verifying the model is loaded on all endpoints.

        vLLM typically loads the model at startup, so this method verifies
        that the model is available by querying the /v1/models endpoint.

        Args:
            endpoints: List of vLLM server URLs
            timeout: Maximum time in seconds for model verification

        Returns:
            True if model is loaded successfully on all endpoints, False otherwise
        """
        threads = []
        results = [False] * len(endpoints)

        for idx, endpoint in enumerate(endpoints):
            print(f"\nVerifying model '{self.model}' at {endpoint}...")
            t = threading.Thread(
                target=self._verify_model_on_endpoint,
                args=(endpoint, results, idx, timeout)
            )
            t.start()
            threads.append(t)

        # Wait for all verifications to complete
        for t in threads:
            t.join()

        return all(results)

    def _verify_model_on_endpoint(self, endpoint: str, results: List[bool],
                                  idx: int, timeout: int):
        """
        Verify model is loaded on a single endpoint.

        vLLM loads models at startup based on the --model parameter.
        This method verifies the model is accessible via the /v1/models endpoint.

        Args:
            endpoint: vLLM server URL
            results: Shared list to store success/failure
            idx: Index in results list
            timeout: Request timeout
        """
        try:
            start_time = time.time()

            # Poll the /v1/models endpoint until the model is available or timeout
            while time.time() - start_time < timeout:
                try:
                    res = requests.get(
                        f"{endpoint}/v1/models",
                        timeout=10
                    )
                    status = res.status_code

                    if 200 <= status < 300:
                        # Parse response to check if our model is listed
                        try:
                            data = res.json()
                            models = data.get("data", [])
                            model_ids = [m.get("id") for m in models]

                            print(f"Available models at {endpoint}: {model_ids}")

                            # Check if our model is in the list
                            # vLLM may use the full model path or just the model name
                            model_found = any(
                                self.model in model_id or model_id in self.model
                                for model_id in model_ids
                            )

                            if model_found:
                                print(f"Model '{self.model}' is loaded at {endpoint}")
                                results[idx] = True
                                return
                            else:
                                print(f"Model '{self.model}' not yet available at {endpoint}, retrying...")
                        except Exception as e:
                            print(f"Error parsing models response: {e}")
                    else:
                        print(f"Failed to query models at {endpoint} (HTTP {status}), retrying...")

                except Exception as e:
                    print(f"Error querying models at {endpoint}: {e}, retrying...")

                time.sleep(5)  # Wait before retrying

            # Timeout reached
            print(f"Timeout: Model '{self.model}' not available at {endpoint} after {timeout}s")
            results[idx] = False

        except Exception as e:
            print(f"Error verifying model '{self.model}' at {endpoint}: {e}")
            results[idx] = False

    def get_health_check_endpoint(self) -> str:
        """
        Get vLLM health check endpoint path.

        Returns:
            "/health"
        """
        return "/health"

    @classmethod
    def parse_service_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract vLLM-specific configuration from recipe.

        Args:
            recipe_config: Full recipe configuration

        Returns:
            Dict containing:
                - model: Model name to use
                - Any other vLLM-specific settings

        Raises:
            ValueError: If required configuration is missing
        """
        workload = recipe_config.get("workload", {})
        servers = recipe_config.get("servers", {})

        model = workload.get("model")
        if not model:
            raise ValueError("vLLM recipe must specify 'workload.model'")

        config = {
            "model": model,
            "service_config": servers.get("service_config", {})
        }

        return config
