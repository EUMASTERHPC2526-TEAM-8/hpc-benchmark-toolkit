import argparse
from benchmark.servers.ollama_server import check_ollama_health, pull_ollama_model
from benchmark.orchestator_clients.ollama_client_lancher import OllamaClientLauncher

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-nodes", type=str, required=True, help="Space-separated list of server node hostnames")
    parser.add_argument("--client-nodes", type=str, required=True, help="Space-separated list of client node hostnames")
    parser.add_argument("--client-port", type=int, default=5000, help="Port for client servers (default: 5000)")
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    server_nodes = args.server_nodes.split()
    client_nodes = args.client_nodes.split()
    service_endpoints = [f"http://{node}:11434" for node in server_nodes]

    # Launch health checks and model pulls
    print(f"Checking Ollama health on endpoints: {service_endpoints}")
    ollama_health = check_ollama_health(service_endpoints, args.timeout)
    if not ollama_health:
        print("Some Ollama endpoints failed health check.")
        exit(1)
    ollama_pull = pull_ollama_model(service_endpoints, args.model, args.timeout)
    if not ollama_pull:
        print("Some Ollama endpoints failed to pull the model.")
        exit(1)
    
    print("All Ollama endpoints healthy and model pulled successfully.")
    
    # Launch clients
    client_launcher = OllamaClientLauncher(client_nodes, port=args.client_port)
    clients_healthy = client_launcher.wait_until_healthy()
    if not clients_healthy:
        print("Some Ollama clients failed health check.")
        exit(1)
    client_success = client_launcher.launch_clients()
    if not client_success:
        print("Some Ollama clients failed to launch.")
        exit(1)
    print("All Ollama clients launched successfully.")
    exit(0)


if __name__ == "__main__":
    main()