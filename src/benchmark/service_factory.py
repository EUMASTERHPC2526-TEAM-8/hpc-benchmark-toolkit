"""
Factory for creating service-specific managers and controllers.

This factory pattern allows the orchestrator to instantiate the correct
server managers and workload controllers based on the service type
specified in the recipe configuration.
"""

from typing import Dict, Any, List
from pathlib import Path 
from benchmark.servers.base_server_manager import BaseServerManager
from benchmark.workload.controller import BaseWorkloadController
from benchmark.workload.executor import BaseWorkloadExecutor
from benchmark.logging.base_log_collector import BaseLogCollector


class ServiceFactory:
    """
    Factory for creating service-specific components.

    Supports:
    - Server managers (orchestrator-side server lifecycle management)
    - Workload controllers (orchestrator-side client coordination)
    - Workload executors (client-side workload execution)
    """

    # Registry of available services
    _server_managers: Dict[str, type] = {}
    _workload_controllers: Dict[str, type] = {}
    _workload_executors: Dict[str, type] = {}
    _log_collectors: Dict[str, type] = {}

    @classmethod
    def register_service(cls, service_name: str,
                        server_manager_class: type,
                        workload_controller_class: type,
                        workload_executor_class: type):
        """
        Register a new service implementation.

        Args:
            service_name: Name of the service (e.g., "ollama", "postgres")
            server_manager_class: Class extending BaseServerManager
            workload_controller_class: Class extending BaseWorkloadController
            workload_executor_class: Class extending BaseWorkloadExecutor
        """
        cls._server_managers[service_name] = server_manager_class
        cls._workload_controllers[service_name] = workload_controller_class
        cls._workload_executors[service_name] = workload_executor_class
        print(f"Registered service: {service_name}")

    @classmethod
    def create_server_manager(cls, service_name: str, config: Dict[str, Any]) -> BaseServerManager:
        """
        Create a server manager for the specified service.

        Args:
            service_name: Name of the service (e.g., "ollama", "postgres")
            config: Service-specific configuration

        Returns:
            Instance of the appropriate ServerManager subclass

        Raises:
            ValueError: If service is not registered
        """
        if service_name not in cls._server_managers:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Available services: {list(cls._server_managers.keys())}"
            )

        manager_class = cls._server_managers[service_name]
        return manager_class(config)


    @classmethod
    def create_workload_controller(cls, service_name: str,
                                   client_nodes: List[str],
                                   port: int = 5000,
                                   timeout: int = 30,
                                   health_timeout: int = 120) -> BaseWorkloadController:
        """
        Create a workload controller for the specified service.

        Args:
            service_name: Name of the service (e.g., "ollama", "postgres")
            client_nodes: List of client node hostnames
            port: Port where workload executors are running
            timeout: Default request timeout
            health_timeout: Health check timeout

        Returns:
            Instance of the appropriate WorkloadController subclass

        Raises:
            ValueError: If service is not registered
        """
        if service_name not in cls._workload_controllers:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Available services: {list(cls._workload_controllers.keys())}"
            )

        controller_class = cls._workload_controllers[service_name]
        return controller_class(client_nodes, port, timeout, health_timeout)

    @classmethod
    def create_workload_executor(cls, service_name: str, port: int = 5000) -> BaseWorkloadExecutor:
        """
        Create a workload executor for the specified service.

        Args:
            service_name: Name of the service (e.g., "ollama", "postgres")
            port: Port to run the Flask server on

        Returns:
            Instance of the appropriate WorkloadExecutor subclass

        Raises:
            ValueError: If service is not registered
        """
        if service_name not in cls._workload_executors:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Available services: {list(cls._workload_executors.keys())}"
            )

        executor_class = cls._workload_executors[service_name]
        return executor_class(port)
    
    @classmethod
    def register_log_collector(cls, collector_type: str, collector_class: type):
        """Register a new log collector implementation."""
        cls._log_collectors[collector_type] = collector_class
        print(f"Registered log collector: {collector_type}")
    
    @classmethod
    def create_log_collector(cls, collector_type: str, 
                            config: Dict[str, Any], 
                            output_dir) -> BaseLogCollector:
        """Create a log collector of the specified type."""
        if collector_type not in cls._log_collectors:
            raise ValueError(
                f"Unknown log collector type: {collector_type}. "
                f"Available types: {list(cls._log_collectors.keys())}"
            )
        
        collector_class = cls._log_collectors[collector_type]
        return collector_class(config, Path(output_dir))
    
    @classmethod
    def list_log_collectors(cls) -> List[str]:
        """List all registered log collectors."""
        return list(cls._log_collectors.keys())
    

    @classmethod
    def list_services(cls) -> List[str]:
        """
        List all registered services.

        Returns:
            List of service names
        """
        return list(cls._server_managers.keys())
