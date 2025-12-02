# HPC Benchmark Toolkit

A comprehensive framework for benchmarking LLM inference services (Ollama, vLLM) on HPC clusters with integrated real-time monitoring.

## Features

- **Multi-service support**: Ollama, vLLM, with extensible architecture
- **Distributed benchmarking**: Multi-node server/client orchestration
- **Real-time monitoring**: CPU, RAM, GPU metrics with Prometheus/Grafana integration
- **HPC-optimized**: Slurm integration, Apptainer/Singularity container support
- **Reproducible experiments**: YAML-based configuration recipes

## Architecture

```
Orchestrator (coordinator)
    ├── Server Manager (health checks, model loading)
    │   └── Ollama/vLLM/Dummy server instances
    ├── Workload Controller (client coordination)
    │   └── Workload Executors (inference requests)
    └── Monitor (metrics collection)
        └── Pushgateway → Prometheus → Grafana
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd hpc-benchmark-toolkit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install flask requests psutil prometheus_client pyyaml
```

### 2. Configure Recipe

Edit `src/src/recipes/ollama_meluxina.yaml`:

```yaml
workload:
  service: "ollama"
  model: "llama2"
  clients_per_node: 10
  duration: "2m"
```

### 3. Run Benchmark

```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"

python3 src/benchmark/orchestrator.py \
  --server-nodes node001 \
  --client-nodes node002 node003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml
```

## Monitoring Setup

For detailed monitoring setup with Grafana visualization:

📖 **See [monitoring/QUICKSTART.md](monitoring/QUICKSTART.md)** for complete guide

**TL;DR:**
1. Start Pushgateway on HPC: `sbatch monitoring/meluxina/start_pushgateway.sh`
2. Start Docker stack locally: `cd monitoring && ./start.sh`
3. Open SSH tunnel: `ssh -N -L 19091:mel2109:9091 user@cluster`
4. Run with monitoring: `--enable-monitoring --pushgateway-node mel2109`
5. View in Grafana: http://localhost:3001

## Project Structure

```
hpc-benchmark-toolkit/
├── src/
│   ├── benchmark/
│   │   ├── orchestrator.py          # Main coordinator
│   │   ├── service_factory.py       # Service creation
│   │   ├── servers/                 # Server managers
│   │   │   ├── ollama_server_manager.py
│   │   │   └── vllm_server_manager.py
│   │   └── workload/
│   │       ├── controller/          # Client coordinators
│   │       └── executor/            # Client workers
│   ├── monitor/
│   │   └── monitor.py               # Metrics collector
│   └── src/
│       └── recipes/                 # Experiment configs
├── monitoring/
│   ├── QUICKSTART.md                # Setup guide
│   ├── docker-compose.yml           # Prometheus/Grafana stack
│   └── meluxina/
│       └── start_pushgateway.sh     # HPC Pushgateway job
└── docs/                            # Architecture docs
```

## CLI Reference

### Orchestrator Arguments

```bash
python3 orchestrator.py \
  --server-nodes NODE [NODE ...]      # Server hostnames
  --client-nodes NODE [NODE ...]      # Client hostnames
  --workload-config-file PATH         # YAML/JSON config
  [--server-port PORT]                # Default: 11434
  [--client-port PORT]                # Default: 5000
  [--timeout SECONDS]                 # Default: 600
  [--enable-monitoring]               # Enable metrics collection
  [--pushgateway-node NODE]           # Required if monitoring enabled
  [--monitor-interval SECONDS]        # Default: 5
  [--monitor-output PATH]             # Default: benchmark_metrics.csv
```

### Example: Distributed Benchmark with Monitoring

```bash
# Terminal 1: Start Pushgateway on cluster
sbatch monitoring/meluxina/start_pushgateway.sh
PG_NODE=$(squeue -u $USER -n pushgateway -h -o %N)

# Terminal 2: Allocate compute nodes
salloc -N 3 -t 01:00:00

# Terminal 3: Run benchmark
export PYTHONPATH="$PWD/src:$PYTHONPATH"
python3 src/benchmark/orchestrator.py \
  --server-nodes mel2001 \
  --client-nodes mel2002 mel2003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml \
  --enable-monitoring \
  --pushgateway-node $PG_NODE \
  --monitor-interval 2 \
  --monitor-output results/run_001.csv

# Terminal 4 (laptop): View live metrics
open http://localhost:3001  # Grafana
```

## Configuration Format

### Minimal Config (JSON)

```json
{
  "service": "ollama",
  "model": "llama2",
  "clients_per_node": 5
}
```

### Full Recipe (YAML)

```yaml
scenario: "ollama-benchmark"
partition: "gpu"
account: "project123"

workload:
  service: "ollama"
  model: "llama2"
  clients_per_node: 10
  duration: "5m"
  warmup: "1m"

resources:
  servers:
    gpus: 2
    cpus_per_task: 4
    mem_gb: 32

artifacts:
  containers_dir: "/path/to/containers/"
  service:
    path: "ollama_latest.sif"
    remote: "docker://ollama/ollama:latest"
```

## Metrics Collected

| Metric | Description | Labels |
|--------|-------------|--------|
| `cpu_usage_percent` | Per-core CPU utilization | `instance`, `job` |
| `ram_used_megabytes` | System memory usage | `instance`, `job` |
| `gpu_utilization_percent` | GPU compute usage | `instance`, `job`, `gpu_id` |
| `gpu_memory_used_megabytes` | GPU memory usage | `instance`, `job`, `gpu_id` |

## Extending the Framework

### Add New Service

1. **Create server manager**: `src/benchmark/servers/myservice_server_manager.py`
2. **Create workload controller**: `src/benchmark/workload/controller/myservice_workload_controller.py`
3. **Create workload executor**: `src/benchmark/workload/executor/myservice_workload_executor.py`
4. **Register service**: Add to `src/benchmark/service_registry.py`

See `dummy_*` implementations for template.

## Requirements

- **Python**: 3.6+
- **HPC**: Slurm workload manager
- **Optional**: Docker (for local Grafana stack)
- **Python packages**: `flask`, `requests`, `psutil`, `prometheus_client`, `pyyaml`

## Troubleshooting

### Server health check fails
```bash
# Verify server is running and accessible
curl http://server-node:11434/api/tags
```

### Monitor not pushing metrics
```bash
# Check Pushgateway is reachable
curl http://pushgateway-node:9091/metrics | grep cpu_usage_percent

# Verify PYTHONPATH is set
echo $PYTHONPATH  # Should include /path/to/hpc-benchmark-toolkit/src
```

### No data in Grafana
```bash
# Check SSH tunnel is active
ps aux | grep "ssh.*19091"

# Verify Prometheus scraping
curl http://localhost:9092/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="hpc-monitor")'
```
