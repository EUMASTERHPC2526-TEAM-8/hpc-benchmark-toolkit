"""
Central registry for all service implementations.
Import and register each service here.
"""

from benchmark.service_factory import ServiceFactory

# Import service implementations
from benchmark.servers.ollama_server_manager import OllamaServerManager
from benchmark.workload.controller import OllamaWorkloadController
from benchmark.workload.executor import OllamaWorkloadExecutor

#import log collector
from benchmark.logging.tailer_log_collector import TailerLogCollector

# Register Ollama service
ServiceFactory.register_service(
    "ollama",
    OllamaServerManager,
    OllamaWorkloadController,
    OllamaWorkloadExecutor
)


# Register vLLM service
from benchmark.servers.vllm_server_manager import VllmServerManager
from benchmark.workload.controller import VllmWorkloadController
from benchmark.workload.executor import VllmWorkloadExecutor

ServiceFactory.register_service(
    "vllm",
    VllmServerManager,
    VllmWorkloadController,
    VllmWorkloadExecutor
)


# Register Dummy service (template/example)
from benchmark.servers.dummy_server_manager import DummyServerManager
from benchmark.workload.controller import DummyWorkloadController
from benchmark.workload.executor import DummyWorkloadExecutor
ServiceFactory.register_service(
    "dummy",
    DummyServerManager,
    DummyWorkloadController,
    DummyWorkloadExecutor
)

# Register tailer log collector
ServiceFactory.register_log_collector("tailer", TailerLogCollector)