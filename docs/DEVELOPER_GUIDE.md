# Developer Guide

This guide provides detailed instructions for extending and customizing the HPC Benchmark Toolkit.

---

## Table of Contents

1. [Architecture Deep Dive](#architecture-deep-dive)
2. [Adding a New Service](#adding-a-new-service)
3. [Customizing Workloads](#customizing-workloads)
4. [Extending the Monitor](#extending-the-monitor)
5. [Custom Log Collectors](#custom-log-collectors)
6. [Recipe Schema Extensions](#recipe-schema-extensions)
7. [Testing](#testing)
8. [Contributing Guidelines](#contributing-guidelines)

---

## Architecture Deep Dive

### Design Patterns

The toolkit uses several design patterns to maintain flexibility and extensibility:

#### Factory Pattern

`ServiceFactory` creates service components dynamically based on service name:

```python
# Registration (service_registry.py)
ServiceFactory.register_service(
    "myservice",
    MyServerManager,
    MyWorkloadController,
    MyWorkloadExecutor
)

# Usage (anywhere in codebase)
manager = ServiceFactory.create_server_manager("myservice", config)
```

#### Template Method Pattern

Base classes define the algorithm skeleton, subclasses provide implementations:

```python
class BaseServerManager:
    def run_health_check(self, endpoints, timeout):
        # Template method
        endpoint_path = self.get_health_check_endpoint()  # Abstract
        for ep in endpoints:
            if not self._check_url(f"http://{ep}{endpoint_path}"):
                return False
        return True

    @abstractmethod
    def get_health_check_endpoint(self) -> str:
        """Subclass provides the endpoint path"""
        pass
```

#### Strategy Pattern

Different workload executors implement service-specific benchmark strategies:

```python
class OllamaWorkloadExecutor(BaseWorkloadExecutor):
    def _run_benchmark(self, config, thread_id):
        # Ollama-specific implementation
        pass

class VllmWorkloadExecutor(BaseWorkloadExecutor):
    def _run_benchmark(self, config, thread_id):
        # vLLM-specific implementation
        pass
```

### Component Lifecycle

```
1. Orchestrator parses recipe
       |
       v
2. ServiceFactory creates ServerManager
       |
       v
3. ServerManager.verify_health() polls servers
       |
       v
4. ServerManager.prepare_service() loads models
       |
       v
5. ServiceFactory creates WorkloadController
       |
       v
6. WorkloadController.verify_client_health() checks executors
       |
       v
7. WorkloadController.start_workload() triggers execution
       |
       v
8. [Benchmark runs for duration]
       |
       v
9. WorkloadController.get_metrics() collects results
       |
       v
10. WorkloadController.stop_workload() terminates
```

---

## Adding a New Service

### Complete Example: Adding "TensorRT" Service

#### Step 1: Create Server Manager

Create `src/benchmark/servers/tensorrt_server_manager.py`:

```python
"""TensorRT Inference Server Manager."""

import time
import requests
from typing import List, Dict, Any
from benchmark.servers.base_server_manager import BaseServerManager


class TensorRTServerManager(BaseServerManager):
    """Manages TensorRT Inference Server lifecycle."""

    DEFAULT_PORT = 8001  # gRPC port
    HTTP_PORT = 8000     # HTTP port for health checks

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize TensorRT server manager.

        Args:
            config: Server configuration from recipe
        """
        self.config = config
        self.health_check_config = config.get('health_check', {})
        self.service_config = self.parse_service_config(
            config.get('service_config', {})
        )

    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Verify all TensorRT server endpoints are healthy.

        Args:
            endpoints: List of server endpoints (host:port)
            timeout: Maximum wait time in seconds

        Returns:
            True if all endpoints are healthy
        """
        interval = self.health_check_config.get('interval', 5)
        start_time = time.time()

        for endpoint in endpoints:
            host = endpoint.split(':')[0]
            url = f"http://{host}:{self.HTTP_PORT}/v2/health/ready"

            while time.time() - start_time < timeout:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        print(f"[TensorRT] Server {endpoint} is healthy")
                        break
                except requests.RequestException:
                    pass

                time.sleep(interval)
            else:
                print(f"[TensorRT] Server {endpoint} health check failed")
                return False

        return True

    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        """
        Prepare TensorRT server (load models).

        For TensorRT, models are typically loaded at server startup
        via model repository. This method verifies models are loaded.

        Args:
            endpoints: Server endpoints
            timeout: Maximum wait time

        Returns:
            True if all models are loaded
        """
        model_name = self.service_config.get('model')
        if not model_name:
            print("[TensorRT] No model specified, skipping model verification")
            return True

        for endpoint in endpoints:
            host = endpoint.split(':')[0]
            url = f"http://{host}:{self.HTTP_PORT}/v2/models/{model_name}/ready"

            try:
                response = requests.get(url, timeout=30)
                if response.status_code != 200:
                    print(f"[TensorRT] Model {model_name} not ready on {endpoint}")
                    return False
            except requests.RequestException as e:
                print(f"[TensorRT] Failed to check model: {e}")
                return False

        print(f"[TensorRT] Model {model_name} ready on all servers")
        return True

    def parse_service_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse TensorRT-specific configuration.

        Args:
            config: Raw service configuration

        Returns:
            Parsed configuration with defaults
        """
        return {
            'model': config.get('model'),
            'model_repository': config.get('model_repository', '/models'),
            'backend': config.get('backend', 'tensorrt'),
            'max_batch_size': config.get('max_batch_size', 8),
            'instance_group_count': config.get('instance_group_count', 1),
            'dynamic_batching': config.get('dynamic_batching', True),
        }

    def get_health_check_endpoint(self) -> str:
        """Return health check endpoint path."""
        return "/v2/health/ready"
```

#### Step 2: Create Workload Controller

Create `src/benchmark/workload/controller/tensorrt_workload_controller.py`:

```python
"""TensorRT Workload Controller."""

from benchmark.workload.controller.base_workload_controller import BaseWorkloadController


class TensorRTWorkloadController(BaseWorkloadController):
    """
    Controls TensorRT workload execution across client nodes.

    Inherits all functionality from BaseWorkloadController.
    Override methods only if TensorRT-specific behavior is needed.
    """

    def __init__(self, client_nodes, port, timeout=600):
        super().__init__(client_nodes, port, timeout)
        self.service_name = "tensorrt"

    # Base class provides:
    # - verify_client_health()
    # - start_workload()
    # - get_metrics()
    # - stop_workload()

    def start_workload(self, workload_config):
        """
        Start TensorRT workload with custom preprocessing.

        Adds TensorRT-specific configuration before calling base method.
        """
        # Add TensorRT-specific defaults
        tensorrt_config = {
            **workload_config,
            'use_grpc': workload_config.get('use_grpc', True),
            'protocol': 'grpc' if workload_config.get('use_grpc', True) else 'http',
        }

        return super().start_workload(tensorrt_config)
```

#### Step 3: Create Workload Executor

Create `src/benchmark/workload/executor/tensorrt_workload_executor.py`:

```python
"""TensorRT Workload Executor."""

import time
import numpy as np
import threading
from typing import Dict, Any, Optional
from benchmark.workload.executor.base_workload_executor import BaseWorkloadExecutor

# Optional: Import TensorRT client
try:
    import tritonclient.grpc as grpcclient
    import tritonclient.http as httpclient
    TRITON_AVAILABLE = True
except ImportError:
    TRITON_AVAILABLE = False


class TensorRTWorkloadExecutor(BaseWorkloadExecutor):
    """Executes TensorRT inference benchmarks on client nodes."""

    def __init__(self, port: int = 6000):
        super().__init__(port)
        self.triton_client: Optional[Any] = None
        self.input_data: Optional[np.ndarray] = None

    def _setup_client(self, server_url: str, use_grpc: bool = True):
        """Initialize Triton client connection."""
        if not TRITON_AVAILABLE:
            raise RuntimeError("tritonclient not installed")

        # Parse server URL
        host = server_url.replace('http://', '').replace('https://', '')
        host = host.split(':')[0]

        if use_grpc:
            self.triton_client = grpcclient.InferenceServerClient(
                url=f"{host}:8001",
                verbose=False
            )
        else:
            self.triton_client = httpclient.InferenceServerClient(
                url=f"{host}:8000",
                verbose=False
            )

    def _prepare_input(self, input_shape: tuple, dtype: str = 'float32'):
        """Prepare input data for inference."""
        # Generate random input based on model requirements
        if dtype == 'float32':
            self.input_data = np.random.randn(*input_shape).astype(np.float32)
        elif dtype == 'int32':
            self.input_data = np.random.randint(0, 100, input_shape).astype(np.int32)
        else:
            self.input_data = np.random.randn(*input_shape).astype(dtype)

    def _run_benchmark(self, workload_config: Dict[str, Any], thread_id: int) -> None:
        """
        Run TensorRT inference benchmark.

        Args:
            workload_config: Configuration including:
                - server_url: TensorRT server URL
                - model: Model name
                - duration: Benchmark duration in seconds
                - input_shape: Model input shape (optional)
                - batch_size: Batch size (optional)
            thread_id: Thread identifier for this worker
        """
        server_url = workload_config['server_url']
        model_name = workload_config.get('model', 'default')
        duration = workload_config.get('duration', 60)
        warmup = workload_config.get('warmup', 10)
        use_grpc = workload_config.get('use_grpc', True)
        batch_size = workload_config.get('batch_size', 1)
        input_shape = workload_config.get('input_shape', (batch_size, 3, 224, 224))

        # Setup client (once per thread)
        try:
            self._setup_client(server_url, use_grpc)
            self._prepare_input(input_shape)
        except Exception as e:
            print(f"[Thread {thread_id}] Setup failed: {e}")
            return

        # Warmup phase
        print(f"[Thread {thread_id}] Starting warmup ({warmup}s)")
        warmup_end = time.time() + warmup
        while time.time() < warmup_end and self.running:
            try:
                self._infer(model_name)
            except Exception:
                pass

        # Benchmark phase
        print(f"[Thread {thread_id}] Starting benchmark ({duration}s)")
        start_time = time.time()
        end_time = start_time + duration

        while time.time() < end_time and self.running:
            request_start = time.time()

            try:
                self._infer(model_name)
                latency = time.time() - request_start

                with self.lock:
                    self.metrics['requests'] += 1
                    self.metrics['latencies'].append(latency)

            except Exception as e:
                with self.lock:
                    self.metrics['errors'] += 1
                print(f"[Thread {thread_id}] Inference error: {e}")

        print(f"[Thread {thread_id}] Benchmark complete")

    def _infer(self, model_name: str):
        """Execute single inference request."""
        if isinstance(self.triton_client, grpcclient.InferenceServerClient):
            # gRPC inference
            inputs = [
                grpcclient.InferInput(
                    "input",
                    self.input_data.shape,
                    "FP32"
                )
            ]
            inputs[0].set_data_from_numpy(self.input_data)

            outputs = [grpcclient.InferRequestedOutput("output")]

            result = self.triton_client.infer(
                model_name=model_name,
                inputs=inputs,
                outputs=outputs
            )
            return result.as_numpy("output")
        else:
            # HTTP inference
            inputs = [
                httpclient.InferInput(
                    "input",
                    self.input_data.shape,
                    "FP32"
                )
            ]
            inputs[0].set_data_from_numpy(self.input_data)

            outputs = [httpclient.InferRequestedOutput("output")]

            result = self.triton_client.infer(
                model_name=model_name,
                inputs=inputs,
                outputs=outputs
            )
            return result.as_numpy("output")

    def get_service_name(self) -> str:
        """Return service name for metrics."""
        return "tensorrt"
```

#### Step 4: Register the Service

Update `src/benchmark/service_registry.py`:

```python
"""Service Registry - Registers all available services."""

from benchmark.service_factory import ServiceFactory

# Import existing services
from benchmark.servers.ollama_server_manager import OllamaServerManager
from benchmark.servers.vllm_server_manager import VllmServerManager
from benchmark.servers.dummy_server_manager import DummyServerManager

# Import new TensorRT service
from benchmark.servers.tensorrt_server_manager import TensorRTServerManager

from benchmark.workload.controller.ollama_workload_controller import OllamaWorkloadController
from benchmark.workload.controller.vllm_workload_controller import VllmWorkloadController
from benchmark.workload.controller.dummy_workload_controller import DummyWorkloadController
from benchmark.workload.controller.tensorrt_workload_controller import TensorRTWorkloadController

from benchmark.workload.executor.ollama_workload_executor import OllamaWorkloadExecutor
from benchmark.workload.executor.vllm_workload_executor import VllmWorkloadExecutor
from benchmark.workload.executor.dummy_workload_executor import DummyWorkloadExecutor
from benchmark.workload.executor.tensorrt_workload_executor import TensorRTWorkloadExecutor


def register_all_services():
    """Register all available services with the factory."""

    # Existing services
    ServiceFactory.register_service(
        "ollama",
        OllamaServerManager,
        OllamaWorkloadController,
        OllamaWorkloadExecutor
    )

    ServiceFactory.register_service(
        "vllm",
        VllmServerManager,
        VllmWorkloadController,
        VllmWorkloadExecutor
    )

    ServiceFactory.register_service(
        "dummy",
        DummyServerManager,
        DummyWorkloadController,
        DummyWorkloadExecutor
    )

    # New TensorRT service
    ServiceFactory.register_service(
        "tensorrt",
        TensorRTServerManager,
        TensorRTWorkloadController,
        TensorRTWorkloadExecutor
    )


# Auto-register on module import
register_all_services()
```

#### Step 5: Create Recipe Example

Create `src/src/recipes/tensorrt_meluxina.yaml`:

```yaml
scenario: "tensorrt-benchmark"
partition: "gpu"
account: "p200981"
qos: "default"

modules:
  - "Apptainer"

orchestration:
  mode: "slurm"
  total_nodes: 3
  node_allocation:
    servers:
      nodes: 1
    clients:
      nodes: 2
      clients_per_node: 8
    monitors:
      nodes: 0
  job_config:
    time_limit: "01:00:00"
    exclusive: true

resources:
  servers:
    gpus: 2
    cpus_per_task: 4
    mem_gb: 32
  clients:
    gpus: 0
    cpus_per_task: 2
    mem_gb: 8

workload:
  component: "inference"
  service: "tensorrt"
  duration: "5m"
  warmup: "30s"
  model: "resnet50"
  clients_per_node: 8
  batch_size: 8
  input_shape: [8, 3, 224, 224]
  use_grpc: true

servers:
  health_check:
    enabled: true
    timeout: 300
    interval: 5
    endpoint: "/v2/health/ready"
  service_config:
    model: "resnet50"
    model_repository: "/models"
    backend: "tensorrt"
    max_batch_size: 32
    dynamic_batching: true

artifacts:
  containers_dir: "/project/home/user/containers/"
  service:
    path: "tritonserver_latest.sif"
    remote: "docker://nvcr.io/nvidia/tritonserver:24.01-py3"
  python:
    path: "python_3_12_3_v2.sif"
    remote: "docker://python:3.12.3-slim"

binds:
  - "/project/home/user/models:/models:ro"
  - "/project/home/user/results:/results:rw"
```

---

## Customizing Workloads

### Custom Dataset Loaders

Create custom dataset loaders for your benchmark:

```python
# src/benchmark/datasets/custom_dataset.py

class CustomDatasetLoader:
    """Load custom prompts/inputs for benchmarking."""

    def __init__(self, path: str):
        self.path = path
        self.data = self._load()

    def _load(self):
        """Load dataset from file."""
        import json
        with open(self.path) as f:
            return json.load(f)

    def get_sample(self, index: int = None):
        """Get a sample from the dataset."""
        import random
        if index is None:
            index = random.randint(0, len(self.data) - 1)
        return self.data[index]

    def __len__(self):
        return len(self.data)


# Usage in executor
class CustomWorkloadExecutor(BaseWorkloadExecutor):
    def _run_benchmark(self, config, thread_id):
        dataset = CustomDatasetLoader(config['dataset_path'])

        while self.running:
            sample = dataset.get_sample()
            # Use sample for inference
```

### Custom Load Patterns

Implement different request distribution patterns:

```python
# src/benchmark/workload/patterns.py

import time
import random
from abc import ABC, abstractmethod


class LoadPattern(ABC):
    """Base class for load patterns."""

    @abstractmethod
    def wait(self) -> None:
        """Wait according to the pattern before next request."""
        pass


class ConstantLoadPattern(LoadPattern):
    """Fixed delay between requests."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay

    def wait(self):
        if self.delay > 0:
            time.sleep(self.delay)


class PoissonLoadPattern(LoadPattern):
    """Poisson-distributed inter-arrival times."""

    def __init__(self, rate: float):
        """
        Args:
            rate: Average requests per second
        """
        self.rate = rate

    def wait(self):
        delay = random.expovariate(self.rate)
        time.sleep(delay)


class BurstLoadPattern(LoadPattern):
    """Burst pattern - send N requests, then pause."""

    def __init__(self, burst_size: int, pause: float):
        self.burst_size = burst_size
        self.pause = pause
        self.count = 0

    def wait(self):
        self.count += 1
        if self.count >= self.burst_size:
            time.sleep(self.pause)
            self.count = 0


# Usage in executor
class AdvancedWorkloadExecutor(BaseWorkloadExecutor):
    def _run_benchmark(self, config, thread_id):
        pattern_type = config.get('request_distribution', 'constant')

        if pattern_type == 'poisson':
            pattern = PoissonLoadPattern(config.get('target_rps', 10))
        elif pattern_type == 'burst':
            pattern = BurstLoadPattern(
                config.get('burst_size', 10),
                config.get('burst_pause', 1.0)
            )
        else:
            pattern = ConstantLoadPattern(config.get('delay', 0))

        while self.running:
            # Make request
            self._make_request()
            pattern.wait()
```

---

## Extending the Monitor

### Adding Custom Metrics

```python
# src/monitor/custom_monitor.py

from monitor.monitor import Monitor
from prometheus_client import Gauge, Counter, Histogram
import subprocess


class CustomMonitor(Monitor):
    """Extended monitor with custom metrics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define custom Prometheus metrics
        self.network_rx = Gauge(
            'network_rx_bytes_total',
            'Network bytes received',
            ['interface']
        )
        self.network_tx = Gauge(
            'network_tx_bytes_total',
            'Network bytes transmitted',
            ['interface']
        )
        self.disk_iops = Gauge(
            'disk_iops',
            'Disk IOPS',
            ['device']
        )

    def collect_metrics(self):
        """Collect all metrics including custom ones."""
        # Call parent method
        super().collect_metrics()

        # Collect custom metrics
        self._collect_network_metrics()
        self._collect_disk_metrics()

    def _collect_network_metrics(self):
        """Collect network interface statistics."""
        try:
            with open('/proc/net/dev') as f:
                for line in f:
                    if ':' in line:
                        parts = line.split(':')
                        iface = parts[0].strip()
                        values = parts[1].split()
                        rx_bytes = int(values[0])
                        tx_bytes = int(values[8])

                        self.network_rx.labels(interface=iface).set(rx_bytes)
                        self.network_tx.labels(interface=iface).set(tx_bytes)
        except Exception as e:
            print(f"Failed to collect network metrics: {e}")

    def _collect_disk_metrics(self):
        """Collect disk I/O statistics."""
        try:
            result = subprocess.run(
                ['iostat', '-d', '-x', '1', '1'],
                capture_output=True,
                text=True
            )
            # Parse iostat output
            # ...
        except Exception:
            pass
```

### Custom Output Formats

```python
# src/monitor/exporters.py

import json
from abc import ABC, abstractmethod


class MetricsExporter(ABC):
    """Base class for metrics exporters."""

    @abstractmethod
    def export(self, metrics: dict) -> None:
        pass


class JSONExporter(MetricsExporter):
    """Export metrics as JSON."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = []

    def export(self, metrics: dict):
        self.data.append(metrics)
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)


class InfluxDBExporter(MetricsExporter):
    """Export metrics to InfluxDB."""

    def __init__(self, url: str, token: str, org: str, bucket: str):
        from influxdb_client import InfluxDBClient
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.bucket = bucket
        self.org = org

    def export(self, metrics: dict):
        from influxdb_client import Point
        write_api = self.client.write_api()

        point = Point("benchmark_metrics")
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                point.field(key, value)

        write_api.write(bucket=self.bucket, org=self.org, record=point)
```

---

## Custom Log Collectors

### Implementing a Remote Log Collector

```python
# src/benchmark/logging/remote_log_collector.py

import paramiko
from typing import List, Dict, Any
from benchmark.logging.base_log_collector import BaseLogCollector, LogSource


class RemoteLogCollector(BaseLogCollector):
    """Collect logs from remote nodes via SSH."""

    def __init__(self, ssh_key_path: str = None):
        self.ssh_key_path = ssh_key_path
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.log_processes: Dict[str, Any] = {}

    def deploy(self) -> bool:
        """No deployment needed for SSH-based collection."""
        return True

    def start_collection(self, sources: List[LogSource]) -> bool:
        """Start collecting logs from all sources."""
        for source in sources:
            try:
                # Connect to node
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    source.node,
                    key_filename=self.ssh_key_path
                )
                self.connections[source.node] = client

                # Start log tailing
                log_path = f"/var/log/{source.component}/{source.container_name}.log"
                stdin, stdout, stderr = client.exec_command(
                    f"tail -f {log_path}",
                    get_pty=True
                )
                self.log_processes[source.node] = (stdout, stderr)

            except Exception as e:
                print(f"Failed to connect to {source.node}: {e}")
                return False

        return True

    def is_ready(self) -> bool:
        """Check if all connections are active."""
        return all(
            conn.get_transport().is_active()
            for conn in self.connections.values()
        )

    def stop_collection(self) -> Dict[str, Any]:
        """Stop collection and return aggregated logs."""
        logs = {}

        for node, (stdout, stderr) in self.log_processes.items():
            # Read available output
            logs[node] = {
                'stdout': stdout.read().decode('utf-8', errors='ignore'),
                'stderr': stderr.read().decode('utf-8', errors='ignore')
            }

        # Close connections
        for client in self.connections.values():
            client.close()

        return logs
```

---

## Recipe Schema Extensions

### Adding New Fields

Update `schemas/recipe-format.yaml`:

```yaml
# Add new top-level field
properties:
  # ... existing properties ...

  advanced:
    type: object
    description: "Advanced configuration options"
    properties:
      retry_policy:
        type: object
        properties:
          max_retries:
            type: integer
            default: 3
          backoff_multiplier:
            type: number
            default: 2.0
      profiling:
        type: object
        properties:
          enabled:
            type: boolean
            default: false
          gpu_profiling:
            type: boolean
            default: false
          trace_output:
            type: string

  # Add new workload field
  workload:
    properties:
      # ... existing properties ...
      custom_field:
        type: string
        description: "Custom workload configuration"
```

### Validation Extensions

Add custom validators:

```python
# src/src/custom_validators.py

def validate_distributed_config(config: dict) -> list:
    """Validate distributed configuration consistency."""
    errors = []

    servers = config.get('orchestration', {}).get('node_allocation', {}).get('servers', {})
    service_config = config.get('servers', {}).get('service_config', {})
    distributed = service_config.get('distributed', {})

    if distributed.get('enabled', False):
        server_nodes = servers.get('nodes', 1)
        tp_size = distributed.get('tensor_parallel_size', 1)
        gpus_per_node = distributed.get('ray', {}).get('num_gpus_per_node', 1)

        total_gpus = server_nodes * gpus_per_node

        if tp_size > total_gpus:
            errors.append(
                f"tensor_parallel_size ({tp_size}) exceeds "
                f"total GPUs ({total_gpus})"
            )

    return errors
```

---

## Testing

### Unit Tests

```python
# tests/test_server_manager.py

import pytest
from unittest.mock import Mock, patch
from benchmark.servers.ollama_server_manager import OllamaServerManager


class TestOllamaServerManager:
    """Test OllamaServerManager functionality."""

    def test_parse_service_config_defaults(self):
        """Test default configuration parsing."""
        manager = OllamaServerManager({})
        config = manager.parse_service_config({})

        assert config.get('gpu_layers') == 0

    def test_parse_service_config_custom(self):
        """Test custom configuration parsing."""
        manager = OllamaServerManager({})
        config = manager.parse_service_config({'gpu_layers': 35})

        assert config.get('gpu_layers') == 35

    @patch('requests.get')
    def test_verify_health_success(self, mock_get):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        manager = OllamaServerManager({
            'health_check': {'interval': 1}
        })
        result = manager.verify_health(['localhost:11434'], timeout=5)

        assert result is True

    @patch('requests.get')
    def test_verify_health_failure(self, mock_get):
        """Test failed health check."""
        mock_get.side_effect = ConnectionError("Connection refused")

        manager = OllamaServerManager({
            'health_check': {'interval': 1}
        })
        result = manager.verify_health(['localhost:11434'], timeout=2)

        assert result is False
```

### Integration Tests

```python
# tests/integration/test_full_workflow.py

import pytest
from benchmark.orchestrator import Orchestrator


@pytest.fixture
def sample_config():
    return {
        'workload': {
            'service': 'dummy',
            'duration': 5,
            'clients_per_node': 1
        },
        'servers': {
            'health_check': {'timeout': 10}
        }
    }


class TestFullWorkflow:
    """Integration tests for complete benchmark workflow."""

    @pytest.mark.integration
    def test_dummy_benchmark(self, sample_config):
        """Test complete workflow with dummy service."""
        orchestrator = Orchestrator(
            server_nodes=['localhost'],
            client_nodes=['localhost'],
            config=sample_config
        )

        result = orchestrator.run()

        assert result['status'] == 'completed'
        assert 'throughput_rps' in result
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run integration tests (requires services)
pytest tests/integration/ -m integration
```

---

## Contributing Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function parameters and return values
- Maximum line length: 100 characters
- Use docstrings for all public classes and methods

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes with appropriate tests
4. Run tests: `pytest tests/`
5. Submit pull request with description

### Commit Messages

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(tensorrt): add TensorRT service support

- Implement TensorRTServerManager
- Add TensorRTWorkloadExecutor with gRPC support
- Create example recipe

Closes #123
```

### Documentation

- Update API Reference for new public interfaces
- Add examples to documentation
- Include docstrings with usage examples

---

## Troubleshooting Development Issues

### Common Issues

#### Import Errors

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH="$PWD/src:$PYTHONPATH"
```

#### Service Not Found

```python
# Ensure service is registered
from benchmark.service_registry import register_all_services
register_all_services()
```

#### Mock Not Working

```python
# Patch the correct path
@patch('benchmark.servers.ollama_server_manager.requests.get')  # Not 'requests.get'
```

---

## Resources

- [Python ABC Module](https://docs.python.org/3/library/abc.html)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Prometheus Client](https://github.com/prometheus/client_python)
- [Ray Documentation](https://docs.ray.io/)
