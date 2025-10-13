"""
Base class for workload execution on client nodes.

This class runs as a Flask server on each client node and executes
the actual benchmark workload (e.g., sending requests to servers,
collecting metrics, etc.).
"""

from abc import ABC, abstractmethod
from flask import Flask, jsonify, request
from typing import Dict, Any, Optional
import threading


class BaseWorkloadExecutor(ABC): # Will be renamed to BaseWorkloadExecutor (workload context)
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
            """Fetch collected metrics."""
            return jsonify({
                "running": self.workload_running,
                "metrics": self.metrics,
                "error": self.workload_error
            }), 200

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
        """
        try:
            num_threads = int(workload_config.get("clients_per_node", 1))
            print(f"Starting benchmark with {num_threads} threads.")
            threads = []

            def thread_target():
                try:
                    self._run_benchmark(workload_config)
                except Exception as e:
                    print(f"Thread error: {e}")

            for i in range(num_threads):
                t = threading.Thread(target=thread_target, name=f"client-thread-{i}")
                t.start()
                threads.append(t)

            for t in threads:
                t.join()
        except Exception as e:
            self.workload_error = str(e)
            print(f"Workload execution error: {e}")
        finally:
            self.workload_running = False

    @abstractmethod
    def _run_benchmark(self, workload_config: Dict[str, Any]):
        """
        Execute the service-specific benchmark workload.

        This method should:
        1. Parse workload_config
        2. Execute benchmark (send requests, etc.)
        3. Collect metrics and store in self.metrics
        4. Respect self.workload_running flag (check it periodically)

        Args:
            workload_config: Configuration dict containing:
                - server_endpoints: List of server URLs to target
                - duration: How long to run
                - Additional service-specific parameters

        The implementation should periodically check self.workload_running
        and stop gracefully if it becomes False.
        """
        pass

    def get_service_name(self) -> str:
        """
        Get the name of the service this executor handles.

        Returns:
            Service name (e.g., "ollama", "postgres")
        """
        return self.__class__.__name__.replace("WorkloadExecutor", "").lower()

    def run(self):
        """Start the Flask server."""
        print(f"Starting {self.get_service_name()} workload executor on port {self.port}...")
        self.app.run(host="0.0.0.0", port=self.port)
