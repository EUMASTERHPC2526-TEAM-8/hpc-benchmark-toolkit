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
    max_duration=60            # Maximum duration in seconds
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
- `prometheus_client>=0.17.0` (required)
- NVIDIA GPU and `nvidia-smi` (for GPU metrics, optional)

## Installation
```bash
pip install -r requirements.txt
```

## Prometheus Integration
Prometheus metrics are always collected internally. You can expose them via an HTTP exporter and/or push them to a Pushgateway (utile per job batch brevi con SLURM).

### Enable Exporter (pull model)
In code:

```python
monitor = Monitor(
        # ... other params ...
        prometheus_port=9100,
        prometheus_addr="0.0.0.0",
        prometheus_start_http_server=True,
)
```

Prometheus scrape config example:

```yaml
scrape_configs:
    - job_name: hpc-monitor
        static_configs:
            - targets: ["node-or-ip:9100"]
```

### Pushgateway (push model)
In code:

```python
monitor = Monitor(
        # ... other params ...
        prometheus_pushgateway_url="http://pushgateway:9091",
        prometheus_grouping_labels={"project": "hpc-benchmark"},
)
```

The monitor automatically pushes metrics every 15 seconds by default. Grouping labels will include host `instance` and `SLURM_JOB_ID` if present.

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
  
Note: Prometheus integration is covered indirectly

## Platform Support
- **Linux**: Full support (CPU, RAM, GPU)
- **macOS**: CPU and RAM only (no NVIDIA GPUs)
- **Windows**: Full support if NVIDIA drivers installed
- **MeLuXina Supercomputer**: Fully compatible; supports CPU, RAM, Disk, GPU, Network I/O, Process Count, and Uptime metrics.


## Collected Metrics

| **Category**           | **Metric Name**               | **Description**                                         |
| ---------------------- | ----------------------------- | ------------------------------------------------------- |
| **CPU**                | `cpu_usage_percent`           | CPU utilization percentage                              |
| **Memory**             | `ram_used_megabytes`          | RAM usage in megabytes                                  |
| **Disk**               | `disk_usage_percent`          | Disk usage percentage (root filesystem)                 |
| **Network I/O**        | `net_bytes_sent_per_second`   | Bytes sent per second across all network interfaces     |
|                        | `net_bytes_recv_per_second`   | Bytes received per second across all network interfaces |
| **Disk I/O**           | `disk_read_bytes_per_second`  | Disk read throughput (bytes per second)                 |
|                        | `disk_write_bytes_per_second` | Disk write throughput (bytes per second)                |
| **Processes**          | `process_count`               | Number of currently running processes                   |
| **Uptime**             | `system_uptime_seconds`       | Total system uptime in seconds                          |
| **GPU (if available)** | `gpu_utilization_percent`     | GPU utilization percentage                              |
|                        | `gpu_memory_used_megabytes`   | GPU memory usage in megabytes                           |



## Data Storage
All collected metrics are stored automatically in two formats inside the output directory
(default: ./monitor_output/):

| **File**        | **Format** | **Description**                                                                                                              |
| --------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `metrics.jsonl` | JSON Lines | Each line contains a timestamped JSON record of all metric values. Ideal for programmatic analysis (e.g., Python or Pandas). |
| `metrics.csv`   | CSV        | A comma-separated version of the same data for quick inspection or spreadsheet visualization.                                |


The exporter also serves metrics in real time for Prometheus scraping at:
👉 http://0.0.0.0:9100/metrics


## Extending
You can add new metrics by extending the monitor script:
- **1**:Define a new Prometheus metric using Gauge, Counter, or Summary.
- **2**:Collect its values inside the sample_metrics() function.
- **3**:Add it to both the JSON/CSV export logic and the Prometheus update section.
- **4**:Example ideas for future extensions:
- **5**:CPU temperature or fan speed
- **6**:GPU power draw or temperature
- **7**:Network latency and packet loss
- **8**:Benchmark-specific performance counters

