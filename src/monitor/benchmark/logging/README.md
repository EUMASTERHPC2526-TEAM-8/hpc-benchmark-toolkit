# Logging Module

This module provides log collection and aggregation for the HPC benchmark framework.

## Architecture

- `BaseLogCollector` - Abstract base class defining the collector interface
- `TailerLogCollector` - Python-based implementation that tails container logs
- `LogSource` - Data class representing a log source (node + component)

## Usage

### Basic Example
```python
from benchmark.logging.tailer_log_collector import TailerLogCollector
from benchmark.logging.base_log_collector import LogSource
from pathlib import Path

# Define log sources
sources = [
    LogSource(node="node123", component="server", container_name="server_123"),
    LogSource(node="node456", component="client", container_name="client_456")
]

# Create collector
config = {
    "type": "tailer",
    "create_jsonl": True,
    "outputs": {
        "stdout": "stdout.log",
        "stderr": "stderr.log",
        "aggregated": "aggregated.jsonl"
    }
}

collector = TailerLogCollector(config, Path("./results"))

# Lifecycle
collector.deploy(sources)
collector.start_collection()
# ... benchmark runs ...
summary = collector.stop_collection()
```

## Output Files

- `stdout.log` - Aggregated stdout with timestamps and metadata
- `stderr.log` - Aggregated stderr (reserved for future use)
- `aggregated.jsonl` - Structured JSON Lines format
- `loggers_ready` - Flag file indicating collector is ready

## Integration

See `INTEGRATION.md` in the repository root for integration instructions.

## Testing

Run the standalone test:
```bash
python examples/test_log_collector.py
```

## Adding New Collectors

To add a new collector type (e.g., Fluent Bit):

1. Create `fluent_bit_log_collector.py` extending `BaseLogCollector`
2. Implement all abstract methods
3. Register in `service_registry.py` when integrated

## Dependencies

- Python 3.7+
- No external dependencies (uses standard library only)