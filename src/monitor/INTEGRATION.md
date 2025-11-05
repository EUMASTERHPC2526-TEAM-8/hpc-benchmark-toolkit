# Logging Module Integration Guide

This document explains how to integrate the Logging module into the benchmark framework.

## What This Module Provides

The Logging module (`benchmark/logging/`) provides:
- `BaseLogCollector` - Abstract base class for log collectors
- `TailerLogCollector` - Python-based log tailing implementation
- `LogSource` - Data class representing log sources

## Integration Steps

### Step 1: Register Log Collectors in ServiceFactory

**File:** `benchmark/service_factory.py`

Add log collector support:
```python
from benchmark.logging.base_log_collector import BaseLogCollector

class ServiceFactory:
    # Add to existing registries
    _log_collectors: Dict[str, type] = {}
    
    @classmethod
    def register_log_collector(cls, collector_type: str, collector_class: type):
        """Register a new log collector implementation."""
        cls._log_collectors[collector_type] = collector_class
        print(f"Registered log collector: {collector_type}")
    
    @classmethod
    def create_log_collector(cls, collector_type: str, 
                            config: Dict[str, Any], 
                            output_dir: Path) -> BaseLogCollector:
        """Create a log collector of the specified type."""
        if collector_type not in cls._log_collectors:
            raise ValueError(f"Unknown log collector type: {collector_type}")
        
        collector_class = cls._log_collectors[collector_type]
        return collector_class(config, output_dir)
```

### Step 2: Register in Service Registry

**File:** `benchmark/service_registry.py`

Add at the end:
```python
# Register log collectors
from benchmark.logging.tailer_log_collector import TailerLogCollector

ServiceFactory.register_log_collector("tailer", TailerLogCollector)
```

### Step 3: Use in Orchestrator

**File:** `benchmark/orchestrator/orchestrator.py`

Add logging lifecycle:
```python
from benchmark.service_factory import ServiceFactory
from benchmark.logging.base_log_collector import LogSource

# After servers are healthy, before clients start:
log_collector = ServiceFactory.create_log_collector(
    collector_type="tailer",
    config=logging_config,
    output_dir=Path(results_dir)
)

sources = [
    LogSource(node=n, component="server", container_name=f"server_{n}")
    for n in server_nodes
]

log_collector.deploy(sources)
log_collector.start_collection()

# ... run benchmark ...

# At the end:
summary = log_collector.stop_collection()
```

## Testing Without Integration

See `examples/test_log_collector.py` for a standalone test.

