# API Reference

This document provides detailed API documentation for all public classes and methods in the HPC Benchmark Toolkit.

---

## Table of Contents

1. [Service Factory](#service-factory)
2. [Server Managers](#server-managers)
3. [Workload Controllers](#workload-controllers)
4. [Workload Executors](#workload-executors)
5. [Monitor](#monitor)
6. [Log Collectors](#log-collectors)
7. [Orchestrator](#orchestrator)

---

## Service Factory

### `ServiceFactory`

Factory class for creating service components.

**Location:** `src/benchmark/service_factory.py`

#### Class Methods

##### `create_server_manager(service_name: str, config: Dict[str, Any]) -> BaseServerManager`

Creates a server manager instance for the specified service.

**Parameters:**
- `service_name` (str): Name of the service ("ollama", "vllm", "dummy")
- `config` (Dict): Service configuration from recipe

**Returns:**
- `BaseServerManager`: Configured server manager instance

**Example:**
```python
from benchmark.service_factory import ServiceFactory

config = {
    'health_check': {'timeout': 300, 'interval': 5},
    'service_config': {'gpu_layers': 0}
}
manager = ServiceFactory.create_server_manager("ollama", config)
```

---

##### `create_workload_controller(service_name: str, client_nodes: List[str], port: int, timeout: int) -> BaseWorkloadController`

Creates a workload controller for coordinating client nodes.

**Parameters:**
- `service_name` (str): Name of the service
- `client_nodes` (List[str]): List of client node hostnames
- `port` (int): Port for client communication
- `timeout` (int): Operation timeout in seconds

**Returns:**
- `BaseWorkloadController`: Configured workload controller

**Example:**
```python
controller = ServiceFactory.create_workload_controller(
    "ollama",
    client_nodes=["node001", "node002"],
    port=5000,
    timeout=600
)
```

---

##### `create_workload_executor(service_name: str, port: int) -> BaseWorkloadExecutor`

Creates a workload executor for running on client nodes.

**Parameters:**
- `service_name` (str): Name of the service
- `port` (int): Port for the Flask server

**Returns:**
- `BaseWorkloadExecutor`: Workload executor instance

**Example:**
```python
executor = ServiceFactory.create_workload_executor("ollama", port=6000)
executor.run()  # Starts Flask server
```

---

##### `register_service(name: str, server_class: Type, controller_class: Type, executor_class: Type) -> None`

Registers a new service type with the factory.

**Parameters:**
- `name` (str): Service name identifier
- `server_class` (Type): Server manager class
- `controller_class` (Type): Workload controller class
- `executor_class` (Type): Workload executor class

**Example:**
```python
ServiceFactory.register_service(
    "myservice",
    MyServiceServerManager,
    MyServiceWorkloadController,
    MyServiceWorkloadExecutor
)
```

---

## Server Managers

### `BaseServerManager`

Abstract base class for all server managers.

**Location:** `src/benchmark/servers/base_server_manager.py`

#### Abstract Methods

##### `verify_health(endpoints: List[str], timeout: int = 600) -> bool`

Verifies that all server endpoints are healthy and ready to accept requests.

**Parameters:**
- `endpoints` (List[str]): List of server endpoints (host:port format)
- `timeout` (int): Maximum time to wait for health check (default: 600s)

**Returns:**
- `bool`: True if all endpoints are healthy

---

##### `prepare_service(endpoints: List[str], timeout: int = 600) -> bool`

Prepares the service for benchmarking (e.g., loading models).

**Parameters:**
- `endpoints` (List[str]): List of server endpoints
- `timeout` (int): Maximum time for preparation

**Returns:**
- `bool`: True if preparation succeeded

---

##### `parse_service_config(config: Dict[str, Any]) -> Dict[str, Any]`

Parses service-specific configuration from recipe.

**Parameters:**
- `config` (Dict): Raw configuration from recipe

**Returns:**
- `Dict`: Parsed configuration with defaults applied

---

##### `get_health_check_endpoint() -> str`

Returns the health check endpoint path for this service.

**Returns:**
- `str`: Health check path (e.g., "/api/tags", "/health")

---

### `OllamaServerManager`

Server manager for Ollama inference service.

**Location:** `src/benchmark/servers/ollama_server_manager.py`

#### Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `gpu_layers` | int | 0 | Number of GPU layers to use |
| `model` | str | - | Model name to load |

#### Health Check

- **Endpoint:** `/api/tags`
- **Default Port:** 11434

#### Example

```python
from benchmark.servers.ollama_server_manager import OllamaServerManager

config = {
    'health_check': {'timeout': 300},
    'service_config': {'gpu_layers': 35, 'model': 'llama2'}
}
manager = OllamaServerManager(config)

# Check health
healthy = manager.verify_health(["node001:11434"], timeout=300)

# Prepare (pull model)
ready = manager.prepare_service(["node001:11434"])
```

---

### `VllmServerManager`

Server manager for vLLM inference service.

**Location:** `src/benchmark/servers/vllm_server_manager.py`

#### Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model` | str | - | Model name/path |
| `max_model_len` | int | 2048 | Maximum sequence length |
| `gpu_memory_utilization` | float | 0.9 | GPU memory fraction to use |
| `enforce_eager` | bool | false | Disable CUDA graphs |
| `trust_remote_code` | bool | false | Allow custom model code |
| `distributed.enabled` | bool | false | Enable distributed mode |
| `distributed.tensor_parallel_size` | int | 1 | Tensor parallelism degree |
| `distributed.pipeline_parallel_size` | int | 1 | Pipeline parallelism degree |

#### Health Check

- **Endpoint:** `/health`
- **Default Port:** 8000

#### Distributed Configuration

```python
config = {
    'service_config': {
        'distributed': {
            'enabled': True,
            'backend': 'ray',
            'tensor_parallel_size': 4,
            'pipeline_parallel_size': 1,
            'ray': {
                'dashboard_port': 8265,
                'num_cpus_per_node': 4,
                'num_gpus_per_node': 2
            }
        }
    }
}
manager = VllmServerManager(config)
```

---

### `RayClusterManager`

Manages Ray cluster for distributed vLLM.

**Location:** `src/benchmark/servers/ray_cluster_manager.py`

#### Methods

##### `start_head_node(port: int = 6379) -> bool`

Starts the Ray head node.

**Parameters:**
- `port` (int): Ray port (default: 6379)

**Returns:**
- `bool`: True if head node started successfully

---

##### `connect_worker(head_address: str) -> bool`

Connects a worker node to the Ray cluster.

**Parameters:**
- `head_address` (str): Head node address (host:port)

**Returns:**
- `bool`: True if worker connected successfully

---

##### `get_head_ip() -> str`

Returns the IP address of the current node.

**Returns:**
- `str`: Local IP address

---

## Workload Controllers

### `BaseWorkloadController`

Abstract base class for workload controllers.

**Location:** `src/benchmark/workload/controller/base_workload_controller.py`

#### Constructor

```python
def __init__(self, client_nodes: List[str], port: int, timeout: int = 600)
```

**Parameters:**
- `client_nodes` (List[str]): Hostnames of client nodes
- `port` (int): Port for client communication
- `timeout` (int): Operation timeout

---

#### Methods

##### `verify_client_health() -> bool`

Checks health of all client executors.

**Returns:**
- `bool`: True if all clients are healthy

**Example:**
```python
controller = OllamaWorkloadController(["node1", "node2"], 6000, 600)
if controller.verify_client_health():
    print("All clients ready")
```

---

##### `start_workload(workload_config: Dict[str, Any]) -> bool`

Starts workload execution on all clients.

**Parameters:**
- `workload_config` (Dict): Workload configuration including:
  - `server_url` (str): URL of the inference server
  - `model` (str): Model to use
  - `duration` (int): Duration in seconds
  - `clients_per_node` (int): Number of concurrent clients
  - `warmup` (int): Warmup period in seconds

**Returns:**
- `bool`: True if workload started on all clients

**Example:**
```python
config = {
    'server_url': 'http://node001:11434',
    'model': 'llama2',
    'duration': 120,
    'clients_per_node': 10,
    'warmup': 30
}
controller.start_workload(config)
```

---

##### `get_metrics() -> Dict[str, Any]`

Retrieves metrics from all client executors.

**Returns:**
- `Dict`: Aggregated metrics from all clients

**Response Format:**
```python
{
    'total_requests': 1000,
    'total_errors': 5,
    'avg_latency': 0.45,
    'p50_latency': 0.40,
    'p90_latency': 0.65,
    'p99_latency': 1.20,
    'throughput_rps': 83.3,
    'per_client': [
        {'node': 'node1', 'requests': 500, ...},
        {'node': 'node2', 'requests': 500, ...}
    ]
}
```

---

##### `stop_workload() -> bool`

Stops workload execution on all clients.

**Returns:**
- `bool`: True if stopped successfully

---

## Workload Executors

### `BaseWorkloadExecutor`

Flask-based workload executor for client nodes.

**Location:** `src/benchmark/workload/executor/base_workload_executor.py`

#### Constructor

```python
def __init__(self, port: int = 5000)
```

**Parameters:**
- `port` (int): Port for Flask server (default: 5000)

---

#### REST API Endpoints

##### `GET /health`

Check executor health status.

**Response:**
```json
{
    "service": "ollama",
    "status": "ok"
}
```

---

##### `POST /start`

Start workload execution.

**Request Body:**
```json
{
    "server_url": "http://node001:11434",
    "model": "llama2",
    "duration": 120,
    "clients_per_node": 10,
    "warmup": 30
}
```

**Response:**
```json
{
    "status": "started",
    "threads": 10
}
```

---

##### `GET /status`

Get current workload status.

**Response:**
```json
{
    "running": true,
    "elapsed_seconds": 45.2,
    "threads_active": 10
}
```

---

##### `GET /metrics`

Get collected metrics.

**Response:**
```json
{
    "requests_total": 450,
    "errors_total": 2,
    "latency": {
        "avg": 0.45,
        "p50": 0.40,
        "p90": 0.65,
        "p99": 1.20
    },
    "throughput_rps": 10.0,
    "elapsed_seconds": 45.0
}
```

---

##### `GET /metrics/prometheus`

Get metrics in Prometheus format.

**Response:**
```
# HELP ollama_requests_total Total requests
# TYPE ollama_requests_total counter
ollama_requests_total 450
# HELP ollama_errors_total Total errors
# TYPE ollama_errors_total counter
ollama_errors_total 2
# HELP ollama_request_latency_seconds Request latency
# TYPE ollama_request_latency_seconds gauge
ollama_request_latency_seconds 0.45
```

---

##### `POST /stop`

Stop workload execution.

**Response:**
```json
{
    "status": "stopped",
    "final_metrics": {...}
}
```

---

#### Abstract Methods (for subclasses)

##### `_run_benchmark(workload_config: Dict, thread_id: int) -> None`

Implements the benchmark logic for a single thread.

**Parameters:**
- `workload_config` (Dict): Workload configuration
- `thread_id` (int): Thread identifier

---

##### `get_service_name() -> str`

Returns the service name for metrics labeling.

**Returns:**
- `str`: Service name

---

### `OllamaWorkloadExecutor`

Executor for Ollama benchmarks.

**Location:** `src/benchmark/workload/executor/ollama_workload_executor.py`

**Features:**
- Uses HellaSwag dataset for prompts
- Supports concurrent client threads
- Collects latency distributions

---

### `VllmWorkloadExecutor`

Executor for vLLM benchmarks.

**Location:** `src/benchmark/workload/executor/vllm_workload_executor.py`

**Features:**
- OpenAI-compatible API
- Supports streaming and non-streaming
- Compatible with distributed vLLM

---

## Monitor

### `Monitor`

System metrics collector.

**Location:** `src/monitor/monitor.py`

#### Constructor

```python
def __init__(
    output_file: str = "metrics.csv",
    interval: float = 1.0,
    metrics: Tuple[str, ...] = ("gpu", "cpu", "ram"),
    prometheus_pushgateway_url: Optional[str] = None,
    prometheus_push_interval: int = 15
)
```

**Parameters:**
- `output_file` (str): Path to CSV output file
- `interval` (float): Sampling interval in seconds
- `metrics` (Tuple): Metrics to collect ("gpu", "cpu", "ram")
- `prometheus_pushgateway_url` (str): Optional Pushgateway URL
- `prometheus_push_interval` (int): Prometheus push interval

---

#### Methods

##### `start() -> None`

Start metrics collection in background thread.

---

##### `stop() -> None`

Stop metrics collection.

---

##### `get_latest() -> Dict[str, Any]`

Get the most recent metrics.

**Returns:**
- `Dict`: Latest metric values

---

#### Example

```python
from monitor.monitor import Monitor

monitor = Monitor(
    output_file="benchmark_metrics.csv",
    interval=1,
    metrics=("gpu", "cpu", "ram"),
    prometheus_pushgateway_url="http://pushgateway:9091",
    prometheus_push_interval=15
)

monitor.start()

# ... run benchmark ...

monitor.stop()
```

---

#### CSV Output Format

```csv
timestamp,gpu0_util,gpu0_mem_used,gpu1_util,gpu1_mem_used,cpu_percent,ram_used_MB
2024-01-01T12:00:00,85.5,10240,82.3,10120,45.2,32768
```

---

## Log Collectors

### `BaseLogCollector`

Abstract base for log collectors.

**Location:** `src/benchmark/logging/base_log_collector.py`

#### Data Classes

##### `LogSource`

```python
@dataclass
class LogSource:
    node: str           # Node hostname
    component: str      # "server", "client", "monitor"
    container_name: str # Container ID/name
```

---

#### Abstract Methods

##### `deploy() -> bool`

Deploy log collection infrastructure.

---

##### `start_collection(sources: List[LogSource]) -> bool`

Start collecting from specified sources.

---

##### `is_ready() -> bool`

Check if collector is ready.

---

##### `stop_collection() -> Dict[str, Any]`

Stop collection and return logs.

---

### `TailerLogCollector`

Follows log files on remote nodes.

**Location:** `src/benchmark/logging/tailer_log_collector.py`

---

## Orchestrator

### Command Line Interface

**Location:** `src/benchmark/orchestrator.py`

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--server-nodes` | Yes | - | Server node hostnames |
| `--client-nodes` | Yes | - | Client node hostnames |
| `--workload-config-file` | Yes | - | Path to recipe YAML/JSON |
| `--server-port` | No | 11434 | Server port |
| `--client-port` | No | 5000 | Client executor port |
| `--timeout` | No | 600 | Operation timeout |
| `--enable-monitoring` | No | False | Enable metrics collection |
| `--pushgateway-node` | No | - | Pushgateway node (required if monitoring) |
| `--monitor-interval` | No | 5 | Metrics sampling interval |
| `--monitor-output` | No | benchmark_metrics.csv | Metrics output file |

---

#### Example Usage

```bash
python3 orchestrator.py \
  --server-nodes mel2001 mel2002 \
  --client-nodes mel2003 mel2004 \
  --workload-config-file recipes/ollama_meluxina.yaml \
  --server-port 11434 \
  --client-port 6000 \
  --timeout 600 \
  --enable-monitoring \
  --pushgateway-node mel2109 \
  --monitor-interval 2 \
  --monitor-output results/metrics.csv
```

---

#### Programmatic Usage

```python
from benchmark.orchestrator import Orchestrator

orchestrator = Orchestrator(
    server_nodes=["mel2001", "mel2002"],
    client_nodes=["mel2003", "mel2004"],
    config_file="recipes/ollama_meluxina.yaml",
    server_port=11434,
    client_port=6000,
    timeout=600
)

# Run benchmark
results = orchestrator.run()
print(f"Throughput: {results['throughput_rps']} req/s")
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `E001` | Server health check failed |
| `E002` | Client health check failed |
| `E003` | Service preparation failed |
| `E004` | Workload start failed |
| `E005` | Metrics collection failed |
| `E006` | Configuration validation failed |
| `E007` | Timeout exceeded |
| `E008` | Network connection failed |

---

## Type Definitions

### Configuration Types

```python
from typing import TypedDict, List, Optional

class HealthCheckConfig(TypedDict):
    enabled: bool
    timeout: int
    interval: int
    endpoint: str

class ServiceConfig(TypedDict):
    gpu_layers: Optional[int]
    distributed: Optional[DistributedConfig]

class DistributedConfig(TypedDict):
    enabled: bool
    backend: str
    tensor_parallel_size: int
    pipeline_parallel_size: int
    ray: RayConfig

class RayConfig(TypedDict):
    dashboard_port: int
    object_manager_port: int
    node_manager_port: int
    num_cpus_per_node: int
    num_gpus_per_node: int

class WorkloadConfig(TypedDict):
    component: str
    service: str
    duration: str
    warmup: str
    model: str
    clients_per_node: int

class ResourceConfig(TypedDict):
    gpus: int
    cpus_per_task: int
    mem_gb: int
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2024 | Initial release |
