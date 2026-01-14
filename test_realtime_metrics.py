#!/usr/bin/env python3
"""
Test script to verify real-time metrics collection during benchmark execution.

Tests:
1. Metrics are initialized at benchmark start
2. Metrics update during execution (every 5 seconds via monitoring loop)
3. Prometheus endpoint exposes metrics in text format
4. Metrics show incremental progress (not just final values)
"""

import sys
import time
import requests
import threading
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from benchmark.workload.executor.dummy_workload_executor import DummyWorkloadExecutor

def test_realtime_metrics():
    """Test real-time metrics collection with dummy executor."""
    print("=" * 60)
    print("Testing Real-Time Metrics Collection")
    print("=" * 60)
    
    # Create dummy executor
    executor = DummyWorkloadExecutor(port=5001)
    
    # Start executor in background thread
    executor_thread = threading.Thread(target=executor.run, daemon=True)
    executor_thread.start()
    
    # Give Flask time to start
    time.sleep(2)
    
    print("\n[1] Starting benchmark with 2 threads for 30 seconds...")
    
    # Start benchmark
    response = requests.post(
        "http://localhost:5001/start",
        json={
            "num_threads": 2,
            "duration": "30s",
            "server_endpoints": ["http://dummy:8000"],
            "model": "dummy"
        }
    )
    
    if response.status_code != 200:
        print(f"ERROR: Failed to start benchmark: {response.text}")
        return False
    
    print(f"✓ Benchmark started: {response.json()}")
    
    # Poll metrics every 3 seconds during execution
    print("\n[2] Monitoring metrics during execution...\n")
    
    metrics_history = []
    poll_count = 0
    start_poll_time = time.time()
    service_prefix = "dummy"  # Prometheus metric prefix derives from get_service_name()

    def parse_prometheus_text(text: str):
        parsed = {}
        for line in text.split("\n"):
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            name = parts[0].split("{")[0]  # strip labels if any
            try:
                parsed[name] = float(parts[1])
            except ValueError:
                continue
        return parsed
    
    while time.time() - start_poll_time < 35:  # Poll for 35 seconds
        try:
            response = requests.get("http://localhost:5001/metrics/prometheus", timeout=5)
            
            if response.status_code == 200:
                metrics = parse_prometheus_text(response.text)
                
                if metrics:
                    poll_count += 1
                    elapsed = time.time() - start_poll_time
                    metrics_history.append((elapsed, metrics.copy()))
                    
                    requests_key = f"{service_prefix}_requests_total"
                    errors_key = f"{service_prefix}_errors_total"
                    throughput_key = f"{service_prefix}_throughput_rps"
                    latency_key = f"{service_prefix}_request_latency_seconds"
                    
                    requests_count = metrics.get(requests_key, 0)
                    errors = metrics.get(errors_key, 0)
                    throughput = metrics.get(throughput_key, 0)
                    avg_latency = metrics.get(latency_key, 0.0) * 1000  # seconds -> ms
                    
                    print(f"Poll #{poll_count} @ {elapsed:.1f}s: "
                          f"{requests_count:.0f} requests, "
                          f"{errors:.0f} errors, "
                          f"{throughput:.2f} rps, "
                          f"{avg_latency:.2f} ms avg")
                    
        except requests.RequestException as e:
            print(f"Poll #{poll_count}: Connection error: {e}")
        
        time.sleep(3)  # Poll every 3 seconds
    
    # Wait a bit more for final metrics
    time.sleep(2)
    
    # Get final metrics
    print("\n[3] Fetching final metrics...")
    try:
        response = requests.get("http://localhost:5001/metrics/prometheus", timeout=5)
        final_metrics_text = response.text
        
        # Parse final metrics
        final_metrics = parse_prometheus_text(final_metrics_text)
        
        requests_key = f"{service_prefix}_requests_total"
        errors_key = f"{service_prefix}_errors_total"
        avg_lat_key = f"{service_prefix}_request_latency_seconds"
        throughput_key = f"{service_prefix}_throughput_rps"
        elapsed_key = f"{service_prefix}_elapsed_seconds"
        
        print(f"\nFinal Metrics:")
        print(f"  Total Requests: {final_metrics.get(requests_key, 0):.0f}")
        print(f"  Total Errors:   {final_metrics.get(errors_key, 0):.0f}")
        print(f"  Avg Latency:    {final_metrics.get(avg_lat_key, 0):.3f}s")
        print(f"  Throughput:     {final_metrics.get(throughput_key, 0):.2f} rps")
        print(f"  Elapsed:        {final_metrics.get(elapsed_key, 0):.1f}s")
        
    except Exception as e:
        print(f"Error fetching final metrics: {e}")
        return False
    
    # Verify real-time metrics
    print("\n[4] Verification:")
    
    if len(metrics_history) < 2:
        print(f"✗ FAILED: Only {len(metrics_history)} metric samples (expected at least 2)")
        return False
    else:
        print(f"✓ Collected {len(metrics_history)} metric samples during execution")
    
    # Check if metrics increased over time
    first_metrics = metrics_history[0][1]
    last_metrics = metrics_history[-1][1]
    
    requests_key = f"{service_prefix}_requests_total"
    first_requests = first_metrics.get(requests_key, 0)
    last_requests = last_metrics.get(requests_key, 0)
    
    if last_requests > first_requests:
        print(f"✓ Metrics increased over time: {first_requests:.0f} → {last_requests:.0f} requests")
    else:
        print(f"✗ FAILED: Metrics did not increase: {first_requests:.0f} → {last_requests:.0f}")
        return False
    
    # Check if Prometheus format is valid
    if f'TYPE {requests_key} counter' in final_metrics_text:
        print(f"✓ Prometheus text format is valid")
    else:
        print(f"✗ FAILED: Invalid Prometheus format")
        return False
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = test_realtime_metrics()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
