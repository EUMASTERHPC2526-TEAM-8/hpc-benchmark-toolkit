"""
Benchmark orchestrator - now using class-based architecture.

This file provides backward compatibility with the old interface
while using the new class-based architecture internally.
"""

import argparse
from benchmark.service_factory import ServiceFactory
import time
import json
import os
import benchmark.service_registry


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
    args = parser.parse_args()

    with open(args.workload_config_file) as f:
        workload_config_input = json.load(f)

    server_nodes = args.server_nodes
    server_port = args.server_port
    client_nodes = args.client_nodes
    client_port = args.client_port

    service = workload_config_input.get("service", "ollama")
    model = workload_config_input.get("model", "")
    clients_per_node = workload_config_input.get("clients_per_node", 1)

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

    # Start workload
    print("\nStarting workload execution...")
    workload_config = {
        "server_endpoints": service_endpoints,
        **workload_config_input
    }

    if not workload_controller.start_workload(workload_config):
        print("Failed to start workload.")
        exit(1)

    print("All clients launched successfully.")

    # Periodically poll /metrics to check if all clients are done
    poll_interval = 10  # seconds
    print("Polling client metrics to check for completion...")
    while True:
        all_metrics = workload_controller.fetch_metrics()
        running_status = [metrics.get("running", True) for metrics in all_metrics.values()]
        print(f"Client running status: {running_status}")
        if all(not running for running in running_status):
            print("All clients have completed the workload.")
            break
        print(f"Waiting {poll_interval} seconds before next poll...")
        time.sleep(poll_interval)

    print("Fetching final metrics from all clients...")
    final_metrics = workload_controller.fetch_metrics()
    print(f"Final metrics: {final_metrics}")
    print("Benchmark complete.")

    try:
        os.remove(args.workload_config_file)
        print(f"Removed config file: {args.workload_config_file}")
    except OSError as e:
        print(f"Error removing config file: {e}")

    
    exit(0)


if __name__ == "__main__":
    main()