"""
Base class for managing benchmark service servers.

This abstract class defines the interface that all service-specific
server managers must implement (e.g., OllamaServerManager, PostgresServerManager).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseServerManager(ABC):
    """
    Abstract base class for managing server lifecycle operations.

    Responsibilities:
    - Verify server health/readiness
    - Initialize/prepare the service (e.g., pull models, load data)
    - Provide service-specific configuration parsing
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the server manager with configuration.

        Args:
            config: Service-specific configuration from the recipe
        """
        self.config = config

    @abstractmethod
    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Verify that all server endpoints are healthy and responsive.

        Args:
            endpoints: List of server endpoint URLs (e.g., ["http://node1:11434"])
            timeout: Maximum time in seconds to wait for health checks

        Returns:
            True if all endpoints are healthy, False otherwise
        """
        pass

    @abstractmethod
    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Prepare the service for benchmark execution.

        This may include:
        - Pulling/loading models (for inference services)
        - Loading datasets
        - Initializing databases
        - Any other service-specific setup

        Args:
            endpoints: List of server endpoint URLs
            timeout: Maximum time in seconds for preparation

        Returns:
            True if preparation succeeded on all endpoints, False otherwise
        """
        pass

    @abstractmethod
    def get_health_check_endpoint(self) -> str:
        """
        Get the service-specific health check endpoint path.

        Returns:
            Path for health check endpoint (e.g., "/api/tags", "/health", "/ping")
        """
        pass

    @classmethod
    @abstractmethod
    def parse_service_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and validate service-specific configuration from recipe.

        Args:
            recipe_config: Full recipe configuration dictionary

        Returns:
            Parsed service-specific configuration

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        pass

    def get_service_name(self) -> str:
        """
        Get the name of the service this manager handles.

        Returns:
            Service name (e.g., "ollama", "postgres")
        """
        return self.__class__.__name__.replace("ServerManager", "").lower()
