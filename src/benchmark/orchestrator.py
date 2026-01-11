"""
Benchmark orchestrator - now using class-based architecture.

This file provides backward compatibility with the old interface
while using the new class-based architecture internally.
"""

import argparse
from pathlib import Path
from benchmark.service_factory import ServiceFactory
import time
import json
import yaml
import os
import sys
import socket
import benchmark.service_registry
from benchmark.logging.base_log_collector import LogSource

def main():
    parser = argparse.ArgumentParser(description="Benchmark Orchestrator")
    parser.add_argument("--server-nodes", type=str, nargs='+', required=True,
                       help="List of server node hostnames")
    parser.add_argument("--server-port", type=int, default=11434,
                       help="Port for server nodes (default: 11434)")
    parser.add_argument("--client-nodes", type=str, nargs='+', required=True,
                       help="List of client node hostnames")
    parser.add_argument("--client-port", type=int, default=5000,
                       help="Port for client servers (default: 5000)")
    parser.add_argument("--timeout", type=int, default=600,
                       help="Timeout in seconds")
    parser.add_argument("--workload-config-file", type=str, required=True,
                       help="Path to the workload configuration file ")
    parser.add_argument("--enable-monitoring", action="store_true",
                       help="Enable system monitoring during benchmark")
    parser.add_argument("--monitor-interval", type=int, default=5,
                       help="Monitoring sample interval in seconds (default: 5)")
    parser.add_argument("--monitor-output", type=str, default="benchmark_metrics.csv",
                       help="Output file for monitoring metrics (default: benchmark_metrics.csv)")
    parser.add_argument("--pushgateway-node", type=str,
                       help="Pushgateway node hostname (e.g., mel2145). Required if --enable-monitoring is used.")
    args = parser.parse_args()
    
    OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./benchmark_output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    # Load config file (supports both JSON and YAML)
    with open(args.workload_config_file) as f:
        if args.workload_config_file.endswith(('.yaml', '.yml')):
            workload_config_input = yaml.safe_load(f)
        else:
            workload_config_input = json.load(f)

    server_nodes = args.server_nodes
    server_port = args.server_port
    client_nodes = args.client_nodes
    client_port = args.client_port

    # Support both flat and nested config formats
    workload = workload_config_input.get("workload", workload_config_input)
    service = workload.get("service", "ollama")
    model = workload.get("model", "")
    clients_per_node = workload.get("clients_per_node", 1)

    print(f"Orchestrating benchmark for service: {service}")
    print(f"Server nodes: {server_nodes}")
    print(f"Client nodes: {client_nodes}")
    print(f"Clients per node: {clients_per_node}")

    # Create server manager using the new class-based architecture
    server_config = {"model": model}
    server_manager = ServiceFactory.create_server_manager(service, server_config)

    # Build service endpoints
    service_endpoints = [f"http://{node}:{server_port}" for node in server_nodes]

    # Verify server health
    print(f"\nChecking {service} health on endpoints: {service_endpoints}")
    if not server_manager.verify_health(service_endpoints, args.timeout):
        print("Some server endpoints failed health check.")
        exit(1)

    # Prepare service (e.g., pull model)
    print(f"\nPreparing {service} service...")
    if not server_manager.prepare_service(service_endpoints, args.timeout):
        print("Service preparation failed.")
        exit(1)

    print(f"All {service} endpoints healthy and prepared successfully.")

    # Initialize monitoring if enabled
    monitor = None
    if args.enable_monitoring:
        if not args.pushgateway_node:
            print("Error: --pushgateway-node is required when --enable-monitoring is used.")
            print("Find your Pushgateway node with: squeue -u $USER -n pushgateway -h -o %N")
            exit(1)
            
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from monitor.monitor import Monitor
            
            pushgateway_node = args.pushgateway_node
            
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(args.monitor_output)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            monitor_config = {
                "output_file": args.monitor_output,
                "interval": args.monitor_interval,
                "log_console": True,
                "export_json": False,
                "metrics": ("gpu", "cpu", "ram"),
                "max_duration": None,  # Run until benchmark completes
                "prometheus_pushgateway_url": f"http://{pushgateway_node}:9091",
                "prometheus_grouping_labels": {
                    "job": "benchmark",
                    "source": "orchestrator",
                    "instance": socket.gethostname()
                }
            }
            
            monitor = Monitor(**monitor_config)
            print(f"\nMonitoring enabled:")
            print(f"  - Output: {args.monitor_output}")
            print(f"  - Interval: {args.monitor_interval}s")
            print(f"  - Pushgateway: http://{pushgateway_node}:9091")
            print(f"  - Starting monitor in background...")
            
            # Start monitor in a separate thread
            import threading
            monitor_thread = threading.Thread(target=monitor.run, daemon=True)
            monitor_thread.start()
            time.sleep(2)  # Give monitor time to initialize
            
        except ImportError as e:
            print(f"Warning: Could not import Monitor: {e}")
            print("Continuing without monitoring...")
            monitor = None
        except Exception as e:
            print(f"Warning: Failed to start monitor: {e}")
            print("Continuing without monitoring...")
            monitor = None

    # Create workload controller using the new architecture
    workload_controller = ServiceFactory.create_workload_controller(
        service,
        client_nodes,
        port=client_port,
        timeout=args.timeout
    )

    # Verify client health
    print("\nVerifying client health...")
    if not workload_controller.verify_client_health():
        print("Some clients failed health check.")
        exit(1)

    print("\n" + "="*60)
    print("Setting up logging...")
    print("="*60)
    
    # Create logging configuration
    logging_config = {
        "type": "tailer",
        "create_jsonl": True,
        "outputs": {
            "stdout": "stdout.log",
            "stderr": "stderr.log", 
            "aggregated": "aggregated.jsonl"
        }
    }
    
    # Create log collector
    log_collector = ServiceFactory.create_log_collector(
        collector_type="tailer",
        config=logging_config,
        output_dir=OUTPUT_DIR
    )
    
    # Define log sources (server and client nodes)
    log_sources = []
    
    # Add server log sources
    for node in server_nodes:
        log_sources.append(LogSource(
            node=node,
            component="server",
            container_name=f"server_{node}"
        ))
    
    # Add client log sources
    for node in client_nodes:
        log_sources.append(LogSource(
            node=node,
            component="client",
            container_name=f"client_{node}"
        ))
    
    # Deploy and start log collection
    print(f"\nDeploying log collector for {len(log_sources)} sources...")
    if not log_collector.deploy(log_sources):
        print("WARNING: Log collector deployment failed, continuing without logging")
        log_collector = None
    else:
        print("Starting log collection...")
        if not log_collector.start_collection():
            print("WARNING: Log collection failed to start")
            log_collector = None
        else:
            print("✓ Log collection active\n")

    # Start workload
    # ----------------------------
    # Benchmark suite execution
    # ----------------------------
    import copy

    def _merge_workload_overrides(workload_config_input: dict, overrides: dict) -> dict:
        """
        Merge per-benchmark overrides into either:
          - workload_config_input["workload"] (preferred nested format), or
          - workload_config_input (flat format)
        Returns a new dict (does not mutate input).
        """
        cfg = copy.deepcopy(workload_config_input)
        if isinstance(cfg.get("workload"), dict):
            cfg["workload"].update(overrides)
        else:
            cfg.update(overrides)
        return cfg

    def _get_suite(workload_config_input: dict) -> list:
        # Support both formats:
        #  - top-level benchmark_suite
        #  - nested workload.benchmark_suite
        if isinstance(workload_config_input.get("workload"), dict) and isinstance(workload_config_input["workload"].get("benchmark_suite"), list):
            return workload_config_input["workload"]["benchmark_suite"]
        if isinstance(workload_config_input.get("benchmark_suite"), list):
            return workload_config_input["benchmark_suite"]
        return []

    def _poll_until_done(poll_interval_s: int = 10):
        print("Polling client metrics to check for completion...")
        while True:
            all_metrics = workload_controller.fetch_metrics()
            running_status = [m.get("running", True) for m in all_metrics.values()]
            print(f"Client running status: {running_status}")
            if all(not r for r in running_status):
                print("All clients have completed the workload.")
                return
            print(f"Waiting {poll_interval_s} seconds before next poll...")
            time.sleep(poll_interval_s)

    def _write_json(path: str, obj: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(obj, f, indent=2)

    # Always include server endpoints in the workload config sent to clients
    base_workload_payload = {
        "server_endpoints": service_endpoints,
        **workload_config_input
    }

    suite = _get_suite(workload_config_input)

    results_dir = os.path.join(OUTPUT_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)

    suite_results = {
        "experiment": {
            "service": service,
            "model": model,
            "server_nodes": server_nodes,
            "server_port": server_port,
            "client_nodes": client_nodes,
            "client_port": client_port,
            "clients_per_node": clients_per_node,
            "output_dir": OUTPUT_DIR,
        },
        "benchmarks": []
    }

    # If no suite is provided, run exactly one benchmark (backward compatible)
    if not suite:
        suite = [{
            "name": "single_run",
            # no overrides; uses whatever is already in workload_config_input
        }]

    for i, bench in enumerate(suite, start=1):
        bench_name = bench.get("name", f"bench_{i}")
        print("\n" + "=" * 60)
        print(f"Running benchmark {i}/{len(suite)}: {bench_name}")
        print("=" * 60)

        # Build per-benchmark config by applying overrides
        per_bench_input = _merge_workload_overrides(workload_config_input, {k: v for k, v in bench.items() if k != "name"})
        workload_payload = {
            "server_endpoints": service_endpoints,
            **per_bench_input
        }

        # Add benchmark identity so executors can include it in their metrics if desired
        if isinstance(workload_payload.get("workload"), dict):
            workload_payload["workload"]["benchmark_name"] = bench_name
        else:
            workload_payload["benchmark_name"] = bench_name

        print("Starting workload execution...")
        if not workload_controller.start_workload(workload_payload):
            print(f"Failed to start workload for benchmark '{bench_name}'.")
            exit(1)

        print("All clients launched successfully.")
        _poll_until_done(poll_interval_s=10)

        print("Fetching final metrics from all clients...")
        final_metrics = workload_controller.fetch_metrics()

        # Save per-benchmark raw metrics
        bench_out_path = os.path.join(results_dir, f"{bench_name}.metrics.json")
        _write_json(bench_out_path, {
            "benchmark_name": bench_name,
            "overrides": {k: v for k, v in bench.items() if k != "name"},
            "client_metrics": final_metrics
        })
        print(f"Saved metrics: {bench_out_path}")

        suite_results["benchmarks"].append({
            "benchmark_name": bench_name,
            "metrics_file": bench_out_path,
            "client_metrics": final_metrics
        })

    # Write suite summary
    suite_out_path = os.path.join(results_dir, "benchmark_suite.summary.json")
    _write_json(suite_out_path, suite_results)
    print("\nBenchmark suite complete.")
    print(f"Suite summary saved: {suite_out_path}")


    # Stop monitor if it was running
    if monitor is not None:
        print("\nStopping monitor...")
        # Monitor will stop when the daemon thread exits with the main program
        print(f"Monitor output saved to: {args.monitor_output}")

    try:
        os.remove(args.workload_config_file)
        print(f"Removed config file: {args.workload_config_file}")
    except OSError as e:
        print(f"Error removing config file: {e}")

    
    
    if log_collector:
        print("\n" + "="*60)
        print("Stopping log collection...")
        print("="*60)
        summary = log_collector.stop_collection()
        print(f"Log collection summary: {summary}")
        print(f"Logs saved to: {OUTPUT_DIR}")
        
    exit(0)


if __name__ == "__main__":
    main()