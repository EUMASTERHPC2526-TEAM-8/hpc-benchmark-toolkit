from benchmark.utility import requests
import time
import threading

def __check_ollama_health(endpoint):
    try:
        print(f"Checking Ollama health at {endpoint}...", flush=True)
        res = requests.get(f"{endpoint}/api/tags", timeout=5)
        status = res.status_code
        data = res.text
        print(f"Health check response from {endpoint}: HTTP {status}, Data: {data}")
        if 200 <= status < 300:
            print(f"Ollama healthy at {endpoint}")
            return True
        else:
            print(f"Ollama unhealthy at {endpoint} (HTTP {status})")
            return False
    except Exception as e:
        print(f"Ollama unreachable at {endpoint}: {e}")
        return False


def __pull_ollama_model(endpoint, model, results, idx, timeout):
    try:
        res = requests.post(f"{endpoint}/api/pull", json={"model": model, "stream": False}, timeout=timeout)
        status = res.status_code
        data = res.text
        if 200 <= status < 300:
            print(f"Pulled model '{model}' at {endpoint}: {data}")
            results[idx] = True
        else:
            print(f"Failed to pull model '{model}' at {endpoint} (HTTP {status})")
            results[idx] = False
    except Exception as e:
        print(f"Error pulling model '{model}' at {endpoint}: {e}")
        results[idx] = False

def pull_ollama_model(endpoints, model, timeout=600):
    threads = []
    results = [False] * len(endpoints)
    for idx, endpoint in enumerate(endpoints):
        print(f"\nPulling model '{model}' from {endpoint}...")
        t = threading.Thread(target=__pull_ollama_model, args=(endpoint, model, results, idx, timeout))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return all(results)

def check_ollama_health(endpoints, timeout=600):
    print(f'Checking health of {len(endpoints)} Ollama endpoints with timeout {timeout}s each...')
    for endpoint in endpoints:
        print(f'\nChecking endpoint: {endpoint}')
        start = time.time()
        healthy = False
        while time.time() - start < timeout:
            healthy = __check_ollama_health(endpoint)
            if healthy:
                break
            time.sleep(2)
        if not healthy:
            print(f"Timeout reached: Ollama endpoint {endpoint} is not healthy.")
            return False
    print("All Ollama endpoints are healthy.")
    return True