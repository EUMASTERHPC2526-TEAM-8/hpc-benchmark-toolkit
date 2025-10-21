# Monitor Module

This module provides a flexible system resource monitor for GPU, CPU, and RAM metrics. It supports CSV and JSON export, error logging, and several configurable options.

## Features
- Monitors GPU utilization and memory (NVIDIA GPUs via nvidia-smi)
- Monitors CPU usage and RAM usage
- Configurable sampling interval and duration
- Output to CSV and/or JSON
- Error logging to file
- Select which metrics to monitor
- Easily extensible

## Usage

```python
from monitor import Monitor

monitor = Monitor(
    output_file="metrics.csv",
    interval=1,                # Sampling interval in seconds
    log_console=True,          # Print metrics to console
    export_json=True,          # Also export to JSON
    metrics=("gpu", "cpu", "ram"), # Metrics to monitor
    max_duration=60,           # Maximum duration in seconds
    error_log_file="monitor_errors.log"
)
monitor.run()
```

## CLI Example
You can run the module directly:

```bash
python monitor.py
```

## Output
- `metrics.csv`: Contains timestamped metrics in CSV format
- `metrics.json`: (optional) Contains metrics in JSON array

## Requirements
- Python 3.x
- `psutil>=5.9.0`
- NVIDIA GPU and `nvidia-smi` (for GPU metrics, optional)

## Installation
```bash
pip install -r requirements.txt
```

## Testing
The module includes comprehensive unit tests in `test_monitor.py`:

```bash
python3 -m unittest test_monitor.py
```

### Test Coverage
- **CPU/RAM metrics**: Tests basic monitoring functionality
- **GPU metrics**: Uses mocks to simulate `nvidia-smi` output (works without physical GPUs)
- **Multi-GPU support**: Tests detection and monitoring of multiple GPUs
- **Error handling**: Tests behavior when nvidia-smi is unavailable
- **Combined metrics**: Tests GPU+CPU+RAM monitoring together

**Note**: Tests work on any system (including Mac) by mocking GPU calls. No physical NVIDIA GPU required for testing.

### Test Status
✅ **All 6 tests passed successfully** (tested on macOS)
- Ran 6 tests in 1.253s - OK

## Platform Support
- **Linux**: Full support (CPU, RAM, GPU)
- **macOS**: CPU and RAM only (no NVIDIA GPUs)
- **Windows**: Full support if NVIDIA drivers installed
- **MeLuXina Supercomputer**: Fully compatible (to be tested still)

## Extending
You can add new metrics by extending the class and adding new methods.

