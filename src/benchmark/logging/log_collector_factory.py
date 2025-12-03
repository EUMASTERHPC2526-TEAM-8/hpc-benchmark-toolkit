"""
Factory for creating log collector instances.
"""

from typing import Dict, Any
from pathlib import Path
from benchmark.logging.base_log_collector import BaseLogCollector
from benchmark.logging.tailer_log_collector import TailerLogCollector

# from benchmark.logging.tailer_log_collector import TailerLogCollector
# from benchmark.logging.fluent_bit_collector import FluentBitCollector


class LogCollectorFactory:
    """
    Factory for creating the right type of log collector.
    
    Similar to how ServiceFactory creates OllamaServerManager or VllmServerManager,
    this creates TailerLogCollector or FluentBitCollector based on config.
    """
    
    @staticmethod
    def create(collector_type: str, config: Dict[str, Any], 
               output_dir: Path) -> BaseLogCollector:
        if collector_type == "tailer":
            return TailerLogCollector(config, output_dir)  # Now works!
        elif collector_type == "fluent_bit":
            raise NotImplementedError("FluentBitCollector coming in future!")
        else:
            raise ValueError(f"Unknown collector type: {collector_type}")
        