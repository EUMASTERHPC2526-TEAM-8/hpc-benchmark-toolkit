# HPC Benchmark Toolkit

**Version:** 1.0
**Last Updated:** December 2025

A comprehensive framework for benchmarking LLM inference services (Ollama, vLLM) on HPC clusters with integrated real-time monitoring. Designed for the MeluXina HPC cluster using Slurm and Apptainer containers.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Installation & Setup](#3-installation--setup)
4. [Quick Start Guide](#4-quick-start-guide)
5. [CLI Reference](#5-cli-reference)
6. [Recipe Configuration](#6-recipe-configuration)
7. [Monitoring & Metrics](#7-monitoring--metrics)
8. [Distributed Benchmarking](#8-distributed-benchmarking)
9. [Extending the Framework](#9-extending-the-framework)
10. [API Reference](#10-api-reference)
11. [Troubleshooting](#11-troubleshooting)
12. [Best Practices](#12-best-practices)

---

## 1. Overview

### 1.1 What is HPC Benchmark Toolkit?

The HPC Benchmark Toolkit is a production-ready framework for:

- **Benchmarking LLM inference services** (Ollama, vLLM) on HPC clusters
- **Real-time monitoring** with Prometheus/Grafana integration
- **Distributed workloads** across multiple nodes with Ray-based tensor/pipeline parallelism
- **Reproducible experiments** through YAML-based configuration recipes

### 1.2 Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Service Support** | Ollama, vLLM (single & distributed), extensible architecture |
| **Distributed Benchmarking** | Multi-node server/client orchestration with Ray |
| **Real-Time Monitoring** | Prometheus/Grafana with live dashboards |
| **Recipe-Driven** | YAML configurations for reproducible experiments |
| **HPC-Optimized** | Slurm integration, Apptainer containers |
| **Comprehensive Metrics** | Latency (p50/p90/p99), throughput, resource utilization |

### 1.3 Supported Services

| Service | Description | Default Port |
|---------|-------------|--------------|
| **Ollama** | Local LLM inference server | 11434 |
| **vLLM** | High-throughput LLM serving (OpenAI-compatible) | 8000 |
| **vLLM Distributed** | Multi-node vLLM with Ray cluster | 8000 |
| **Dummy** | Template for custom service implementation | 5000 |

---

## 2. Architecture

### 2.1 High-Level Design

```
                         User
                          |
                          v
                    Interface Layer
              (Recipe Validation & Orchestration)
                          |
         +----------------+----------------+
         v                v                v
    +---------+     +---------+     +---------+
    | Servers |     | Clients |     | Monitors|
    +----+----+     +----+----+     +----+----+
         |               |               |
         +---------------+---------------+
                         |
                         v
              Cluster (SLURM / Kubernetes)
```

### 2.2 Component Overview

```
Orchestrator (Python CLI / benchmark_cli.py)
    +-- Server Manager (health checks, model loading)
    |   +-- Ollama/vLLM/Dummy server instances
    +-- Workload Controller (client coordination)
    |   +-- Workload Executors (inference requests)
    +-- Monitor (metrics collection)
        +-- Pushgateway -> Prometheus -> Grafana
```

### 2.3 Execution Flow

The framework executes benchmarks in 7 phases:

1. **Initialization**: User submits YAML recipe; Interface validates configuration
2. **Service Deployment**: Servers module deploys service container; Health checks verify readiness
3. **Monitoring Setup**: Monitors and Logs modules initialize collection
4. **Client Launch**: Clients module deploys client containers on client nodes
5. **Execution**: Benchmark runs; clients send requests; metrics collected in parallel
6. **Teardown**: Clients/services/monitoring stopped; data aggregated
7. **Report Generation**: Summary statistics and visualizations produced

### 2.4 Project Structure

```
hpc-benchmark-toolkit/
+-- src/
|   +-- benchmark/                      # Core benchmarking framework
|   |   +-- orchestrator.py             # Main coordinator
|   |   +-- service_factory.py          # Factory pattern for services
|   |   +-- service_registry.py         # Service registration
|   |   +-- servers/                    # Server lifecycle management
|   |   |   +-- base_server_manager.py
|   |   |   +-- ollama_server_manager.py
|   |   |   +-- vllm_server_manager.py
|   |   |   +-- dummy_server_manager.py
|   |   |   +-- ray_cluster_manager.py
|   |   +-- workload/
|   |   |   +-- controller/             # Orchestrator-side coordination
|   |   |   |   +-- base_workload_controller.py
|   |   |   |   +-- ollama_workload_controller.py
|   |   |   |   +-- vllm_workload_controller.py
|   |   |   +-- executor/               # Client-side execution
|   |   |       +-- base_workload_executor.py
|   |   |       +-- ollama_workload_executor.py
|   |   |       +-- vllm_workload_executor.py
|   |   +-- logging/                    # Log collection framework
|   +-- benchmark_cli.py                # CLI for recipe management
|   +-- monitor/
|   |   +-- monitor.py                  # System metrics collector
|   +-- src/
|       +-- recipes/                    # Example benchmark recipes
|       +-- generate_sbatch_simple.py   # SLURM script generation
|       +-- validate_recipe.py          # Recipe validation
+-- monitoring/
|   +-- docker-compose.yml              # Prometheus + Grafana stack
|   +-- prometheus.yml                  # Prometheus configuration
|   +-- QUICKSTART.md                   # Monitoring setup guide
|   +-- grafana/
|       +-- dashboards/                 # Pre-built dashboards
+-- schemas/
|   +-- recipe-format.yaml              # JSON Schema for validation
+-- docs/                               # Additional documentation
+-- diagrams/                           # Architecture diagrams (Mermaid)
```

---

## 3. Installation & Setup

### 3.1 Prerequisites

- **Python**: 3.6+
- **HPC Access**: Slurm workload manager, Apptainer/Singularity
- **Optional**: Docker (for local Grafana stack)

### 3.2 Installation

```bash
# Clone repository
git clone <repo-url>
cd hpc-benchmark-toolkit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install flask requests psutil prometheus_client pyyaml
```

### 3.3 SSH Configuration (for MeluXina)

Add to `~/.ssh/config`:

```
Host meluxina
    HostName login.lxp.lu
    Port 8822
    User YOUR_USERNAME
    IdentityFile ~/.ssh/id_ed25519_mlux
```

Test connection:
```bash
ssh meluxina "echo Connected as \$USER"
```

### 3.4 Container Setup

Build or pull containers on the login node:

```bash
# On MeluXina login node
module load Apptainer

# Pull Ollama container
apptainer pull docker://ollama/ollama:latest

# Pull vLLM container
apptainer pull docker://vllm/vllm-openai:latest

# Pull Python container for clients
apptainer pull docker://python:3.12.3-slim
```

---

## 4. Quick Start Guide

### 4.1 Run Your First Benchmark

```bash
# Set Python path
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Run with default recipe
python3 src/benchmark/orchestrator.py \
  --server-nodes node001 \
  --client-nodes node002 node003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml
```

### 4.2 Using the CLI

```bash
# List available recipes
python3 src/benchmark_cli.py list

# Create a new recipe interactively
python3 src/benchmark_cli.py create

# Deploy and run a recipe
python3 src/benchmark_cli.py run --recipe src/src/recipes/ollama_meluxina.yaml
```

### 4.3 Quick Benchmark with Monitoring

```bash
# Terminal 1: Start local monitoring stack
cd monitoring && ./start.sh

# Terminal 2: Run benchmark with monitoring enabled
python3 src/benchmark/orchestrator.py \
  --server-nodes mel2001 \
  --client-nodes mel2002 mel2003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml \
  --enable-monitoring \
  --pushgateway-node mel2109 \
  --monitor-interval 2

# Terminal 3: Open SSH tunnel for metrics
ssh -fN -L 25000:mel2002:6000 meluxina

# View metrics in Grafana
open http://localhost:3001
```

---

## 5. CLI Reference

### 5.1 benchmark_cli.py Commands

#### List Recipes
```bash
python3 src/benchmark_cli.py list
```

Displays all available recipes with their configurations.

#### Create Recipe
```bash
python3 src/benchmark_cli.py create
```

Interactive wizard to create new recipes. Guides through:
- Service selection (Ollama, vLLM, vLLM Distributed)
- Scenario configuration
- Node allocation
- Resource requirements
- Workload parameters
- Container paths

#### Run Recipe
```bash
python3 src/benchmark_cli.py run [--recipe PATH]
```

Deploys and runs a recipe on the HPC cluster:
1. Generates sbatch script from recipe
2. Copies files to cluster
3. Submits job to Slurm

### 5.2 orchestrator.py Arguments

```bash
python3 orchestrator.py \
  --server-nodes NODE [NODE ...]      # Required: Server hostnames
  --client-nodes NODE [NODE ...]      # Required: Client hostnames
  --workload-config-file PATH         # Required: YAML/JSON config
  [--server-port PORT]                # Default: 11434 (Ollama), 8000 (vLLM)
  [--client-port PORT]                # Default: 5000
  [--timeout SECONDS]                 # Default: 600
  [--enable-monitoring]               # Enable metrics collection
  [--pushgateway-node NODE]           # Required if monitoring enabled
  [--monitor-interval SECONDS]        # Default: 5
  [--monitor-output PATH]             # Default: benchmark_metrics.csv
```

---

## 6. Recipe Configuration

### 6.1 Recipe Structure

Recipes are YAML files that define benchmark configurations:

```yaml
scenario: "experiment-name"           # Unique identifier
partition: "gpu"                      # Slurm partition
account: "p200981"                    # Project account
qos: "default"                        # QoS setting (optional)
modules:                              # HPC modules to load
  - "Apptainer"
repetitions: 1                        # Number of repeats (optional)

orchestration:
  mode: "slurm"                       # slurm or kubernetes
  total_nodes: 5
  node_allocation:
    servers:
      nodes: 2
    clients:
      nodes: 2
      clients_per_node: 10
      distribution_strategy: "round-robin"
    monitors:
      nodes: 1
  job_config:
    time_limit: "02:00:00"
    exclusive: true

resources:
  servers:
    gpus: 2
    cpus_per_task: 1
    mem_gb: 32
  clients:
    gpus: 0
    cpus_per_task: 2
    mem_gb: 16
  monitors:
    cpus_per_task: 4
    mem_gb: 8

workload:
  component: "inference"
  service: "ollama"                   # ollama, vllm
  duration: "2m"
  warmup: "1m"
  model: "llama2"
  clients_per_node: 10

servers:
  health_check:
    enabled: true
    timeout: 300
    interval: 5
    endpoint: "/api/tags"
  service_config:
    gpu_layers: 0

artifacts:
  containers_dir: "/path/to/containers/"
  service:
    path: "ollama_latest.sif"
    remote: "docker://ollama/ollama:latest"
  python:
    path: "python_3_12_3_v2.sif"
    remote: "docker://python:3.12.3-slim"

binds:
  - "/project/path/.ollama:/root/.ollama:rw"
  - "/project/path/scratch:/scratch:rw"

metadata:
  seed: 42
  git_commit: "abc123def"
  notes: "experiment notes"
```

### 6.2 Distributed vLLM Configuration

For distributed vLLM with Ray, add to `servers.service_config`:

```yaml
servers:
  health_check:
    enabled: true
    timeout: 600
    interval: 10
    endpoint: "/health"
  service_config:
    distributed:
      enabled: true
      backend: "ray"
      tensor_parallel_size: 4         # GPUs for tensor parallelism
      pipeline_parallel_size: 1       # Stages for pipeline parallelism
      ray:
        dashboard_port: 8265
        object_manager_port: 8076
        node_manager_port: 8077
        num_cpus_per_node: 4
        num_gpus_per_node: 2
    max_model_len: 2048
    gpu_memory_utilization: 0.7
    enforce_eager: true
    trust_remote_code: false
```

### 6.3 Parameter Sweeps

Arrays in fields automatically expand into multiple trials:

```yaml
workload:
  batch: [1, 4, 8]                    # Expands to 3 trials
  concurrency: [1, 8, 32]             # Combined: 9 total trials
  prompt_len: [128, 512]              # Combined: 18 total trials
```

### 6.4 Validation Rules

Recipes are validated against the schema:

- **Required fields**: `scenario`, `partition`, `account`, `resources`, `workload`, `orchestration`
- **Service must be**: `ollama`, `vllm`, or registered custom service
- **Resource values**: Must be positive integers
- **Container path**: Must end in `.sif`
- **GPU partition**: If `gpus > 0`, partition should be `gpu`

---

## 7. Monitoring & Metrics

### 7.1 Monitoring Architecture

```
+------------------------------------------------------------------+
|                        MeluXina HPC                               |
|  +-------------+  +-------------+  +-------------+               |
|  |  Server     |  |   Client    |  | Orchestrator|               |
|  |   Node      |<-|  Executor   |<-|             |               |
|  |   :11434    |  |   :6000     |  |             |               |
|  +-------------+  +------+------+  +-------------+               |
|                          |                                        |
+------------------------------------------------------------------+
                           | SSH Tunnel
                           | -L 25000:client:6000
                           v
+------------------------------------------------------------------+
|                         Laptop                                    |
|  +-------------+       +-------------+                           |
|  |  Prometheus |------>|   Grafana   |                           |
|  |   :9092     | scrape|   :3001     |                           |
|  +------+------+       +-------------+                           |
|         |                                                         |
|         v scrapes localhost:25000/metrics/prometheus              |
+------------------------------------------------------------------+
```

### 7.2 Starting the Monitoring Stack

```bash
# Start Prometheus + Grafana
cd monitoring
./start.sh

# Services available at:
# - Grafana:    http://localhost:3001 (admin/admin)
# - Prometheus: http://localhost:9092
```

### 7.3 Setting Up SSH Tunnel

```bash
# Get client node from job allocation
ssh meluxina "squeue -u \$USER -o '%N' -h"

# Open tunnel (replace melXXXX with actual client node)
ssh -fN -L 25000:melXXXX:6000 meluxina

# Verify tunnel
curl http://localhost:25000/health
```

### 7.4 Available Metrics

#### System Metrics (from Monitor)

| Metric | Description | Labels |
|--------|-------------|--------|
| `cpu_usage_percent` | Per-core CPU utilization | `instance`, `job` |
| `ram_used_megabytes` | System memory usage | `instance`, `job` |
| `gpu_utilization_percent` | GPU compute usage | `instance`, `job`, `gpu_id` |
| `gpu_memory_used_megabytes` | GPU memory usage | `instance`, `job`, `gpu_id` |

#### Workload Metrics (from Executors)

| Metric | Description | Type |
|--------|-------------|------|
| `ollama_workload_running` | 1 if running, 0 if complete | Gauge |
| `ollama_requests_total` | Total requests made | Counter |
| `ollama_errors_total` | Total errors | Counter |
| `ollama_request_latency_seconds` | Average latency | Gauge |
| `ollama_throughput_rps` | Requests per second | Gauge |
| `ollama_elapsed_seconds` | Total elapsed time | Gauge |
| `ollama_threads` | Concurrent threads | Gauge |

### 7.5 Prometheus Queries

```promql
# Check if workload is running
ollama_workload_running

# Total requests
ollama_requests_total

# Throughput
ollama_throughput_rps

# Latency
ollama_request_latency_seconds

# Error count
ollama_errors_total
```

---

## 8. Distributed Benchmarking

### 8.1 vLLM with Ray Cluster

The framework supports distributed vLLM deployment using Ray for tensor and pipeline parallelism.

#### Architecture

```
+-------------------+     +-------------------+
|   Ray Head Node   |     |  Ray Worker Node  |
|   (Server Node 0) |<--->|  (Server Node 1)  |
|                   |     |                   |
|   vLLM Server     |     |   Ray Worker      |
|   :8000           |     |                   |
+-------------------+     +-------------------+
         ^
         |
    Inference Requests
         |
+-------------------+
|   Client Nodes    |
|   (Executors)     |
+-------------------+
```

#### Configuration

```yaml
orchestration:
  node_allocation:
    servers:
      nodes: 2                        # Ray head + 1 worker

servers:
  service_config:
    distributed:
      enabled: true
      backend: "ray"
      tensor_parallel_size: 4         # Total GPUs for tensor parallelism
      pipeline_parallel_size: 1       # Pipeline stages
      ray:
        dashboard_port: 8265
        num_cpus_per_node: 4
        num_gpus_per_node: 2
```

### 8.2 Multi-Node Client Distribution

Distribute load across multiple client nodes:

```yaml
orchestration:
  node_allocation:
    clients:
      nodes: 4
      clients_per_node: 10            # 40 total concurrent clients
      distribution_strategy: "round-robin"  # Options: round-robin, random, all-to-all, static
```

---

## 9. Extending the Framework

### 9.1 Adding a New Service

To add a new service (e.g., `myservice`), implement three components:

#### Step 1: Server Manager

Create `src/benchmark/servers/myservice_server_manager.py`:

```python
from benchmark.servers.base_server_manager import BaseServerManager
from typing import List, Dict, Any

class MyServiceServerManager(BaseServerManager):
    """Manages MyService server lifecycle."""

    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        """Check if all server endpoints are healthy."""
        for endpoint in endpoints:
            url = f"http://{endpoint}/health"
            # Implement health check logic
            if not self._check_endpoint(url, timeout):
                return False
        return True

    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        """Prepare service (load models, initialize)."""
        # Implement preparation logic
        return True

    def parse_service_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse service-specific configuration."""
        return {
            'custom_option': config.get('custom_option', 'default'),
        }

    def get_health_check_endpoint(self) -> str:
        return "/health"
```

#### Step 2: Workload Controller

Create `src/benchmark/workload/controller/myservice_workload_controller.py`:

```python
from benchmark.workload.controller.base_workload_controller import BaseWorkloadController

class MyServiceWorkloadController(BaseWorkloadController):
    """Controls workload execution for MyService."""

    # Base class provides:
    # - verify_client_health()
    # - start_workload(workload_config)
    # - get_metrics()
    # - stop_workload()

    # Override if custom behavior needed
    pass
```

#### Step 3: Workload Executor

Create `src/benchmark/workload/executor/myservice_workload_executor.py`:

```python
from benchmark.workload.executor.base_workload_executor import BaseWorkloadExecutor
from typing import Dict, Any

class MyServiceWorkloadExecutor(BaseWorkloadExecutor):
    """Executes workload on client nodes for MyService."""

    def _run_benchmark(self, workload_config: Dict[str, Any], thread_id: int) -> None:
        """Run benchmark logic for a single thread."""
        server_url = workload_config.get('server_url')
        duration = workload_config.get('duration', 60)

        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                # Make request to service
                response = requests.post(f"{server_url}/api/generate", json={...})

                # Record metrics
                with self.lock:
                    self.metrics['requests'] += 1
                    self.metrics['latencies'].append(response.elapsed.total_seconds())
            except Exception as e:
                with self.lock:
                    self.metrics['errors'] += 1

    def get_service_name(self) -> str:
        return "myservice"
```

#### Step 4: Register Service

Add to `src/benchmark/service_registry.py`:

```python
from benchmark.servers.myservice_server_manager import MyServiceServerManager
from benchmark.workload.controller.myservice_workload_controller import MyServiceWorkloadController
from benchmark.workload.executor.myservice_workload_executor import MyServiceWorkloadExecutor

ServiceFactory.register_service(
    "myservice",
    MyServiceServerManager,
    MyServiceWorkloadController,
    MyServiceWorkloadExecutor
)
```

### 9.2 Adding Custom Metrics

Extend the Monitor class to collect custom metrics:

```python
from monitor.monitor import Monitor
from prometheus_client import Gauge

class CustomMonitor(Monitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_metric = Gauge('custom_metric', 'Description')

    def collect_custom(self):
        value = self._get_custom_value()
        self.custom_metric.set(value)
```

### 9.3 Adding a Log Collector

Implement custom log collection:

```python
from benchmark.logging.base_log_collector import BaseLogCollector, LogSource
from typing import List

class CustomLogCollector(BaseLogCollector):
    def deploy(self) -> bool:
        """Deploy log collection infrastructure."""
        return True

    def start_collection(self, sources: List[LogSource]) -> bool:
        """Start collecting from specified sources."""
        return True

    def is_ready(self) -> bool:
        """Check if collector is ready."""
        return True

    def stop_collection(self) -> Dict[str, Any]:
        """Stop collection and return aggregated logs."""
        return {'logs': [...]}
```

---

## 10. API Reference

### 10.1 ServiceFactory

Factory for creating service components:

```python
from benchmark.service_factory import ServiceFactory

# Create server manager
manager = ServiceFactory.create_server_manager("ollama", config)

# Create workload controller
controller = ServiceFactory.create_workload_controller(
    "ollama",
    client_nodes=["node1", "node2"],
    port=5000,
    timeout=600
)

# Create workload executor
executor = ServiceFactory.create_workload_executor("ollama", port=5000)
```

### 10.2 BaseServerManager

Abstract base class for server managers:

```python
class BaseServerManager(ABC):
    @abstractmethod
    def verify_health(self, endpoints: List[str], timeout: int) -> bool: ...

    @abstractmethod
    def prepare_service(self, endpoints: List[str], timeout: int) -> bool: ...

    @abstractmethod
    def parse_service_config(self, config: Dict) -> Dict: ...

    @abstractmethod
    def get_health_check_endpoint(self) -> str: ...
```

### 10.3 BaseWorkloadController

Abstract base class for workload controllers:

```python
class BaseWorkloadController(ABC):
    def verify_client_health(self) -> bool: ...
    def start_workload(self, workload_config: Dict) -> bool: ...
    def get_metrics(self) -> Dict[str, Any]: ...
    def stop_workload(self) -> bool: ...
```

### 10.4 BaseWorkloadExecutor

Flask-based executor with REST API:

```python
# Endpoints
GET  /health              # Check executor status
POST /start               # Start workload with JSON config
GET  /status              # Get current workload status
GET  /metrics             # Fetch collected metrics
GET  /metrics/prometheus  # Prometheus-compatible metrics
POST /stop                # Stop workload execution
```

### 10.5 Monitor

Metrics collection class:

```python
from monitor.monitor import Monitor

monitor = Monitor(
    output_file="metrics.csv",
    interval=1,                           # Sampling interval (seconds)
    metrics=("gpu", "cpu", "ram"),
    prometheus_pushgateway_url="http://pushgateway:9091",
    prometheus_push_interval=15
)

monitor.start()
# ... benchmark runs ...
monitor.stop()
```

---

## 11. Troubleshooting

### 11.1 Server Health Check Fails

```bash
# Verify server is running and accessible
curl http://server-node:11434/api/tags    # Ollama
curl http://server-node:8000/health       # vLLM

# Check container logs
ssh server-node "tail -f /path/to/logs/server.log"
```

### 11.2 Client Cannot Connect

```bash
# Verify client executor is running
curl http://client-node:6000/health

# Check if port is open
ssh client-node "ss -tulpn | grep 6000"
```

### 11.3 Monitor Not Pushing Metrics

```bash
# Check Pushgateway is reachable
curl http://pushgateway-node:9091/metrics | grep cpu_usage_percent

# Verify PYTHONPATH is set
echo $PYTHONPATH  # Should include /path/to/hpc-benchmark-toolkit/src
```

### 11.4 No Data in Grafana

```bash
# 1. Check Prometheus targets
open http://localhost:9092/targets
# All targets should show "UP"

# 2. Verify SSH tunnel is active
ps aux | grep "ssh.*25000"

# 3. Check metrics endpoint
curl http://localhost:25000/metrics/prometheus
```

### 11.5 Job Stuck in PENDING

```bash
# Check GPU availability
ssh meluxina "sinfo -p gpu"

# Check account permissions
ssh meluxina "sacctmgr show assoc user=\$USER format=account,partition"
```

### 11.6 Ray Cluster Issues (Distributed vLLM)

```bash
# Check Ray head node
ssh head-node "ray status"

# View Ray dashboard
ssh -L 8265:head-node:8265 meluxina
open http://localhost:8265

# Check worker connections
ssh head-node "ray node"
```

---

## 12. Best Practices

### 12.1 Recipe Design

- **Start small**: Begin with minimal configurations for debugging
- **Use meaningful names**: Scenario names should describe the experiment
- **Pin containers**: Use specific digests for reproducibility
- **Include metadata**: Add seed, git_commit, and notes for tracking

### 12.2 Resource Management

- **Match partition to resources**: Use GPU partition when requesting GPUs
- **Account for overhead**: Leave headroom for system processes
- **Monitor utilization**: Use metrics to optimize resource allocation

### 12.3 Benchmarking

- **Warmup period**: Always include warmup to stabilize performance
- **Multiple runs**: Use `repetitions` for statistical significance
- **Consistent environment**: Ensure exclusive node access with `exclusive: true`

### 12.4 Monitoring

- **Start monitoring early**: Initialize before benchmark starts
- **Appropriate intervals**: 1-5 seconds for detailed analysis, 15+ for long runs
- **Save raw data**: Keep CSV files for post-analysis

### 12.5 Data Management

- **Use $WORK for datasets**: Larger quota than $HOME
- **Organize by scenario**: Results in `$WORK/results/<scenario>/<trial_id>/`
- **Archive completed experiments**: Move to long-term storage after analysis

---

## Appendix A: File Reference

| Path | Purpose |
|------|---------|
| `src/benchmark_cli.py` | Main CLI interface |
| `src/benchmark/orchestrator.py` | Experiment orchestrator |
| `src/benchmark/service_factory.py` | Service component factory |
| `src/benchmark/service_registry.py` | Service registration |
| `src/benchmark/servers/*.py` | Server manager implementations |
| `src/benchmark/workload/controller/*.py` | Workload controllers |
| `src/benchmark/workload/executor/*.py` | Workload executors |
| `src/monitor/monitor.py` | Metrics collection |
| `src/src/recipes/*.yaml` | Example recipes |
| `src/src/validate_recipe.py` | Recipe validation |
| `src/src/generate_sbatch_simple.py` | Slurm script generation |
| `schemas/recipe-format.yaml` | Recipe JSON schema |
| `monitoring/docker-compose.yml` | Monitoring stack |
| `monitoring/prometheus.yml` | Prometheus configuration |

---

## Appendix B: Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONPATH` | Python module path (must include `src/`) | - |
| `MLUX_USER` | MeluXina username | - |
| `MLUX_ACCOUNT` | MeluXina project account | - |
| `MLUX_KEY` | Path to SSH key | `~/.ssh/id_ed25519_mlux` |

---

## Appendix C: Ports Reference

| Port | Service | Description |
|------|---------|-------------|
| 11434 | Ollama | Default Ollama API port |
| 8000 | vLLM | Default vLLM API port |
| 5000/6000 | Executor | Workload executor Flask server |
| 9091 | Pushgateway | Prometheus Pushgateway |
| 9092 | Prometheus | Prometheus server |
| 3001 | Grafana | Grafana dashboard |
| 6379 | Ray | Ray cluster communication |
| 8265 | Ray Dashboard | Ray monitoring interface |
| 8076 | Ray Object Manager | Ray object store |
| 8077 | Ray Node Manager | Ray node management |

---

## License

This project is licensed under the terms specified in the LICENSE file.

## Contributing

Contributions are welcome. Please follow the extension guidelines in Section 9 when adding new services or components.

## Support

For issues and feature requests, please use the project's issue tracker.
