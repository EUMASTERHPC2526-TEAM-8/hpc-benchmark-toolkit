#!/usr/bin/env python3
"""
Ollama Server Health Check Module

Checks Ollama server health and lists available models.
The actual Ollama server runs in a container.
"""

import argparse
import time
import sys
from pathlib import Path


def check_ollama_health_and_list_models(host='localhost', port=11434, timeout=120):
    """Check Ollama API health and list available models."""
    import urllib.request
    import urllib.error
    import json
    
    def wait_for_ollama():
        url = f'http://{host}:{port}/api/tags'
        start_time = time.time()
        
        print(f'Waiting for Ollama API at {url}...', flush=True)
        while time.time() - start_time < timeout:
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        print('✓ Ollama API is ready!', flush=True)
                        return True
            except (urllib.error.URLError, urllib.error.HTTPError, Exception):
                pass
            
            elapsed = int(time.time() - start_time)
            print(f'  Still waiting... ({elapsed}s / {timeout}s)', flush=True)
            time.sleep(5)
        
        print('✗ Timeout waiting for Ollama API', flush=True)
        return False

    def list_models():
        try:
            url = f'http://{host}:{port}/api/tags'
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get('models', [])
                
                print(f'\n======= OLLAMA MODELS AVAILABLE =======', flush=True)
                if models:
                    for model in models:
                        name = model.get('name', 'unknown')
                        size = model.get('size', 0)
                        modified = model.get('modified_at', 'unknown')
                        print(f'  📦 {name} ({size//1024//1024} MB, modified: {modified})', flush=True)
                else:
                    print('  No models found', flush=True)
                print(f'======================================\n', flush=True)
                return True
        except Exception as e:
            print(f'✗ Error listing models: {e}', flush=True)
            return False

    # Main execution
    if wait_for_ollama():
        list_models()
        print('✓ Ollama setup complete', flush=True)
        return True
    else:
        print('✗ Failed to connect to Ollama', flush=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check Ollama server health and list models"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=11434,
        help="Port for API server (default: 11434)"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for API server (default: localhost)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds to wait for API (default: 120)"
    )

    # Keep these for compatibility with existing calls, but ignore them
    parser.add_argument("--experiment-id", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", help=argparse.SUPPRESS)
    parser.add_argument("--model", help=argparse.SUPPRESS)
    parser.add_argument("--gpu-layers", help=argparse.SUPPRESS)
    parser.add_argument("--log-endpoints", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--check-only", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Perform health check and list models
    success = check_ollama_health_and_list_models(
        host=args.host, 
        port=args.port, 
        timeout=args.timeout
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()