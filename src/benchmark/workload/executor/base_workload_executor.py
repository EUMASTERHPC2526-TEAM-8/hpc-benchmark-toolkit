"""
Base class for workload execution on client nodes.

This class runs as a Flask server on each client node and executes
the actual benchmark workload (e.g., sending requests to servers,
collecting metrics, etc.).
"""

from abc import ABC, abstractmethod
from flask import Flask, jsonify, request, Response
from typing import Dict, Any, Optional, List
import threading

class BaseWorkloadExecutor(ABC):
    """
    Abstract base class for workload execution on client nodes.

    This runs as a Flask HTTP server that receives commands from the
    orchestrator's WorkloadController and executes service-specific
    benchmark workloads.

    Responsibilities:
    - Expose HTTP endpoints for orchestrator control
    - Execute service-specific benchmark logic
    - Collect and report metrics
    """

    def __init__(self, port: int = 5000):
        """
        Initialize the workload executor.

        Args:
            port: Port to run the Flask server on
        """
        self.port = port
        self.app = Flask(self.__class__.__name__)
        self.workload_thread: Optional[threading.Thread] = None
        self.workload_running = False
        self.metrics: Dict[str, Any] = {}
        self.workload_error: Optional[str] = None

        # Thread-safe metrics collection
        self.metrics_lock = threading.Lock()
        self.thread_metrics: List[Dict[str, Any]] = []

        # Shared resources for workload execution
        self.shared_resources: Dict[str, Any] = {}

        # Register Flask endpoints
        self._register_endpoints()

    def _register_endpoints(self):
        """Register Flask HTTP endpoints."""

        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok", "service": self.get_service_name()}), 200

        @self.app.route("/start", methods=["POST"])
        def start_workload():
            """Start workload execution."""
            if self.workload_running:
                return jsonify({
                    "success": False,
                    "error": "Workload already running"
                }), 400

            try:
                workload_config = request.get_json()
                if not workload_config:
                    return jsonify({
                        "success": False,
                        "error": "No workload configuration provided"
                    }), 400

                # Reset state
                self.metrics = {}
                self.workload_error = None
                self.workload_running = True
                self.thread_metrics = []
                self.shared_resources = {}

                # Start workload in background thread
                self.workload_thread = threading.Thread(
                    target=self._workload_wrapper,
                    args=(workload_config,)
                )
                self.workload_thread.start()

                return jsonify({
                    "success": True,
                    "message": "Workload started"
                }), 200

            except Exception as e:
                self.workload_running = False
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500

        @self.app.route("/metrics", methods=["GET"])
        def get_metrics():
            """Fetch collected metrics in Prometheus format in JSON format (legacy endpoint)."""
            # Check Accept header for content negotiation
            accept = request.headers.get('Accept', '')
            
            # If Prometheus is scraping or explicit prometheus format requested
            if 'text/plain' in accept or request.args.get('format') == 'prometheus':
                return self._metrics_prometheus_format(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
            
            # Default JSON format for orchestrator
            return jsonify({
                "running": self.workload_running,
                "metrics": self.metrics,
                "error": self.workload_error
            }), 200

        @self.app.route("/metrics/prometheus", methods=["GET"])
        def get_metrics_prometheus():
            """Fetch collected metrics in Prometheus text format."""
            return self._metrics_prometheus_format(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

        @self.app.route("/stop", methods=["POST"])
        def stop_workload():
            """Stop workload execution."""
            if not self.workload_running:
                return jsonify({
                    "success": True,
                    "message": "No workload running"
                }), 200

            try:
                self.workload_running = False
                if self.workload_thread and self.workload_thread.is_alive():
                    # Wait for thread to finish (with timeout)
                    self.workload_thread.join(timeout=10)

                return jsonify({
                    "success": True,
                    "message": "Workload stopped"
                }), 200

            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500

    def _workload_wrapper(self, workload_config: Dict[str, Any]):
        """
        Wrapper for running workload in a thread. Supports multithreaded client simulation.

        New flow:
        1. Prepare shared benchmark state (hook _prepare_shared_resources)
        2. Spawn N worker threads that run _run_benchmark
        3. Join threads and aggregate metrics
        """
        try:
            num_threads = int(workload_config.get("num_threads", workload_config.get("clients_per_node", 1)))
            print(f"Starting benchmark with {num_threads} threads.")

            # Prepare shared resources once before spawning threads (can be overridden by subclasses)
            self._prepare_shared_resources(workload_config)

            threads = []

            def thread_target(thread_idx: int):
                try:
                    print(f"Starting benchmark thread {thread_idx}: model={workload_config.get('model')}, "
                          f"servers={len(workload_config.get('server_endpoints', []))}, "
                          f"duration={workload_config.get('duration')}", flush=True)

                    # Each thread collects its own metrics
                    thread_metrics = self._run_benchmark(workload_config, thread_idx)

                    # Store thread metrics in thread-safe manner
                    if thread_metrics:
                        with self.metrics_lock:
                            self.thread_metrics.append(thread_metrics)

                except Exception as e:
                    print(f"Thread {thread_idx} error: {e}")
                    with self.metrics_lock:
                        self.thread_metrics.append({"error": str(e), "thread_id": thread_idx})

            for i in range(num_threads):
                t = threading.Thread(target=thread_target, args=(i,), name=f"client-thread-{i}")
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            # Aggregate metrics from all threads
            self._aggregate_metrics(workload_config)

        except Exception as e:
            self.workload_error = str(e)
            print(f"Workload execution error: {e}")
        finally:
            self.workload_running = False

    def _prepare_shared_resources(self, workload_config: Dict[str, Any]):
        """
        Hook to prepare shared resources before spawning worker threads.

        This is called once before threads are spawned and can be used to:
        - Load datasets once instead of per thread
        - Initialize shared state
        - Set up any resources that all threads will use

        Subclasses should override this to set up shared_resources dict.

        Args:
            workload_config: The workload configuration
        """
        pass

    @abstractmethod
    def _run_benchmark(self, workload_config: Dict[str, Any], thread_id: int) -> Dict[str, Any]:
        """
        Execute the service-specific benchmark workload for a single thread.

        This method should:
        1. Parse workload_config
        2. Execute benchmark (send requests, etc.)
        3. Collect thread-local metrics and return them
        4. Respect self.workload_running flag (check it periodically)
        5. Use self.shared_resources for any pre-loaded data

        Args:
            workload_config: Configuration dict containing:
                - server_endpoints: List of server URLs to target
                - duration: How long to run
                - Additional service-specific parameters
            thread_id: ID of this worker thread

        Returns:
            Dict containing metrics for this thread

        The implementation should periodically check self.workload_running
        and stop gracefully if it becomes False.
        """
        pass

    def _aggregate_metrics(self, workload_config: Dict[str, Any]):
        """
        Aggregate metrics from all threads into self.metrics.

        This is called after all threads have completed. Default implementation
        sums up common metrics. Subclasses can override for custom aggregation.

        Args:
            workload_config: The workload configuration
        """
        if not self.thread_metrics:
            self.metrics = {"error": "No metrics collected from threads"}
            return

        # Default aggregation: sum numeric values
        total_requests = 0
        total_errors = 0
        total_latency = 0.0
        total_elapsed = 0.0
        error_threads = []
        all_latencies = []

        for thread_metric in self.thread_metrics:
            if "error" in thread_metric:
                error_threads.append(thread_metric)
                continue

            total_requests += thread_metric.get("total_requests", 0)
            total_errors += thread_metric.get("errors", 0)
            total_latency += thread_metric.get("total_latency", 0.0)
            total_elapsed = max(total_elapsed, thread_metric.get("elapsed_seconds", 0.0))
            all_latencies.extend(thread_metric.get("latencies", []))

        # Calculate aggregate metrics
        avg_latency = total_latency / total_requests if total_requests > 0 else 0
        throughput = total_requests / total_elapsed if total_elapsed > 0 else 0

        # Percentiles (p50/p90/p99) over all recorded request latencies
        all_latencies.sort()

        def percentile(p: float) -> float:
            if not all_latencies:
                return 0.0
            # nearest-rank style index
            idx = int(round((p / 100.0) * (len(all_latencies) - 1)))
            return all_latencies[idx]

        p50 = percentile(50)
        p90 = percentile(90)
        p99 = percentile(99)


        self.metrics = {
            "total_requests": total_requests,
            "errors": total_errors,
            "elapsed_seconds": total_elapsed,
            "avg_latency_seconds": avg_latency,
            "p50_latency_seconds": p50,  
            "p90_latency_seconds": p90, 
            "p99_latency_seconds": p99, 
            "throughput_rps": throughput,
            "num_threads": len(self.thread_metrics),
            "thread_errors": error_threads if error_threads else None,
            **{k: v for k, v in workload_config.items() if k in ["model", "duration"]}
        }

    def get_service_name(self) -> str:
        """
        Get the name of the service this executor handles.

        Returns:
            Service name (e.g., "ollama", "postgres")
        """
        return self.__class__.__name__.replace("WorkloadExecutor", "").lower()

    def _metrics_prometheus_format(self) -> str:
        """
        Convert metrics to Prometheus text format.
        
        Returns:
            Metrics in Prometheus exposition format
        """
        import socket
        hostname = socket.gethostname()
        service = self.get_service_name()
        
        lines = []
        
        # Running status
        running_val = 1 if self.workload_running else 0
        lines.append(f'# HELP {service}_workload_running Whether the workload is currently running')
        lines.append(f'# TYPE {service}_workload_running gauge')
        lines.append(f'{service}_workload_running{{host="{hostname}"}} {running_val}')
        
        if self.metrics:
            # Total requests
            if 'total_requests' in self.metrics:
                lines.append(f'# HELP {service}_requests_total Total number of requests made')
                lines.append(f'# TYPE {service}_requests_total counter')
                lines.append(f'{service}_requests_total{{host="{hostname}"}} {self.metrics["total_requests"]}')
            
            # Errors
            if 'errors' in self.metrics:
                lines.append(f'# HELP {service}_errors_total Total number of errors')
                lines.append(f'# TYPE {service}_errors_total counter')
                lines.append(f'{service}_errors_total{{host="{hostname}"}} {self.metrics["errors"]}')
            
            # Latency
            if 'avg_latency_seconds' in self.metrics:
                lines.append(f'# HELP {service}_request_latency_seconds Average request latency in seconds')
                lines.append(f'# TYPE {service}_request_latency_seconds gauge')
                lines.append(f'{service}_request_latency_seconds{{host="{hostname}"}} {self.metrics["avg_latency_seconds"]}')
            
            # Throughput
            if 'throughput_rps' in self.metrics:
                lines.append(f'# HELP {service}_throughput_rps Requests per second')
                lines.append(f'# TYPE {service}_throughput_rps gauge')
                lines.append(f'{service}_throughput_rps{{host="{hostname}"}} {self.metrics["throughput_rps"]}')
            
            # Elapsed time
            if 'elapsed_seconds' in self.metrics:
                lines.append(f'# HELP {service}_elapsed_seconds Total elapsed time in seconds')
                lines.append(f'# TYPE {service}_elapsed_seconds gauge')
                lines.append(f'{service}_elapsed_seconds{{host="{hostname}"}} {self.metrics["elapsed_seconds"]}')
            
            # Number of threads
            if 'num_threads' in self.metrics:
                lines.append(f'# HELP {service}_threads Number of concurrent threads')
                lines.append(f'# TYPE {service}_threads gauge')
                lines.append(f'{service}_threads{{host="{hostname}"}} {self.metrics["num_threads"]}')
        
        return '\n'.join(lines) + '\n'

    def run(self):
        """Start the Flask server."""
        print(f"Starting {self.get_service_name()} workload executor on port {self.port}...")
        self.app.run(host="0.0.0.0", port=self.port)
