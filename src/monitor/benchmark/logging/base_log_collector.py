"""
Base class for log collectors.

This abstract class defines the interface that all log collector
implementations must follow (e.g., TailerLogCollector, FluentBitLogCollector).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LogSource:
    """
    Represents a single source of logs to collect.
    
    Attributes:
        node: Node hostname where logs are generated
        component: Type of component ("server", "client", "monitor")
        container_name: Name/ID of the container producing logs
    """
    node: str
    component: str
    container_name: str


class BaseLogCollector(ABC):
    """
    Abstract base class for managing log collection operations.
    
    Responsibilities:
    - Deploy log collection infrastructure
    - Collect and aggregate logs from distributed sources
    - Provide structured log storage and retrieval
    """
    
    def __init__(self, config: Dict[str, Any], output_dir: Path):
        """
        Initialize the log collector with configuration.
        
        Args:
            config: Log collector-specific configuration
            output_dir: Directory where logs should be written
        """
        self.config = config
        self.output_dir = output_dir
        self.running = False
    
    @abstractmethod
    def deploy(self, sources: List[LogSource]) -> bool:
        """
        Deploy log collection infrastructure.
        
        This prepares the collector to start capturing logs from the
        specified sources (e.g., opening files, starting background processes).
        
        Args:
            sources: List of log sources to collect from
            
        Returns:
            True if deployment succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def start_collection(self) -> bool:
        """
        Start collecting logs from all deployed sources.
        
        This begins the actual log capture and aggregation process.
        
        Returns:
            True if collection started successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if log collector is ready to collect logs.
        
        This checks for the "loggers_ready" flag file or other readiness
        indicators.
        
        Returns:
            True if ready, False otherwise
        """
        pass
    
    @abstractmethod
    def stop_collection(self) -> Dict[str, Any]:
        """
        Stop log collection and finalize outputs.
        
        This performs cleanup, flushes buffers, closes files, and returns
        a summary of the collected logs.
        
        Returns:
            Dictionary with collection summary/metadata
        """
        pass
    
    def get_collector_type(self) -> str:
        """
        Get the type of this log collector.
        
        Returns:
            Collector type (e.g., "tailer", "fluent_bit")
        """
        return self.__class__.__name__.replace("LogCollector", "").lower()
    
    @classmethod
    @abstractmethod
    def parse_collector_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and validate log collector configuration from recipe.
        
        Args:
            recipe_config: Full recipe configuration dictionary
            
        Returns:
            Parsed collector-specific configuration
            
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        pass