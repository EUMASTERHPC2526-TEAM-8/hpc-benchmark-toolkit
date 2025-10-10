import time
from benchmark.utility import requests
import json

class OllamaClientLauncher:
    def __init__(self, client_nodes, port=5000, timeout=30, health_timeout=120):
        self.client_nodes = client_nodes
        self.port = port
        self.timeout = timeout
        self.health_timeout = health_timeout  # seconds to wait for health

    def wait_until_healthy(self):
        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/health"
            print(f"Waiting for client node {node} to be healthy at {url} ...")
            start = time.time()
            while time.time() - start < self.health_timeout:
                try:
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200:
                        print(f"Client node {node} is healthy.")
                        break
                except Exception as e:
                    print(f"Client node {node} not healthy yet: {e}")
                time.sleep(2)
            else:
                print(f"ERROR: Client node {node} did not become healthy in time.")
                return False
        return True

    def launch_clients(self):
        all_success = True
        for node in self.client_nodes:
            url = f"http://{node}:{self.port}/launch_ollama_clients"
            try:
                print(f"Calling Ollama client endpoint: {url}")
                resp = requests.post(url, timeout=self.timeout)
                data = json.loads(resp.text)
                if resp.status_code == 200 and data.get("success"):
                    print(f"Client on {node} launched successfully.")
                else:
                    print(f"Client on {node} failed: {resp.text}")
                    all_success = False
            except Exception as e:
                print(f"Error contacting client on {node}: {e}")
                all_success = False
        return all_success