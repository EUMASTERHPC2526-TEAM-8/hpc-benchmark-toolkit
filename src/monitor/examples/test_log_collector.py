"""
Standalone test for the Logging module.

This demonstrates the logging module functionality without requiring
integration into the full benchmark framework.
"""
import sys
import time
from pathlib import Path

# Add parent directory to path so we can import benchmark module
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.logging.tailer_log_collector import TailerLogCollector
from benchmark.logging.base_log_collector import LogSource


def create_fake_logs(output_dir: Path):
    """Create fake log files to simulate server/client output."""
    print("Creating fake log files...")
    
    server_log = output_dir / "container_node123.log"
    client_log = output_dir / "client_node456.log"
    
    # Write initial content
    with open(server_log, 'w') as f:
        f.write("Server starting on port 11434\n")
        f.write("Model loaded successfully\n")
        f.flush()
    
    with open(client_log, 'w') as f:
        f.write("Client connecting to server\n")
        f.write("Sending first request\n")
        f.flush()
    
    return server_log, client_log


def append_to_logs(server_log: Path, client_log: Path):
    """Simulate ongoing log generation."""
    with open(server_log, 'a') as f:
        f.write("Processing request from client\n")
        f.flush()
    
    with open(client_log, 'a') as f:
        f.write("Received response from server\n")
        f.write("Latency: 250ms\n")
        f.flush()


def main():
    print("="*60)
    print("Logging Module Standalone Test")
    print("="*60)
    
    # Setup
    test_dir = Path("./test_logging_output")
    test_dir.mkdir(exist_ok=True)
    
    print(f"\nTest directory: {test_dir}")
    
    # Create fake logs
    server_log, client_log = create_fake_logs(test_dir)
    
    # Define log sources
    sources = [
        LogSource(
            node="node123",
            component="server",
            container_name="test_server"
        ),
        LogSource(
            node="node456",
            component="client",
            container_name="test_client"
        )
    ]
    
    print(f"\nLog sources: {len(sources)}")
    for src in sources:
        print(f"  - {src.component} on {src.node}")
    
    # Create log collector
    config = {
        "type": "tailer",
        "create_jsonl": True,
        "flush_interval": 5,
        "outputs": {
            "stdout": "stdout.log",
            "stderr": "stderr.log",
            "aggregated": "aggregated.jsonl"
        }
    }
    
    print("\nCreating TailerLogCollector...")
    collector = TailerLogCollector(config, test_dir)
    
    # Deploy
    print("\nDeploying collector...")
    if not collector.deploy(sources):
        print("ERROR: Failed to deploy")
        return 1
    
    # Start collection
    print("\nStarting collection...")
    if not collector.start_collection():
        print("ERROR: Failed to start collection")
        return 1
    
    # Verify ready
    if not collector.is_ready():
        print("ERROR: Collector not ready")
        return 1
    
    print("\n✓ Log collection running")
    print("\nSimulating ongoing log generation for 5 seconds...")
    
    # Simulate ongoing logs
    for i in range(5):
        time.sleep(1)
        append_to_logs(server_log, client_log)
        print(f"  Generated logs at t={i+1}s")
    
    # Stop collection
    print("\nStopping log collection...")
    summary = collector.stop_collection()
    
    # Print summary
    print("\n" + "="*60)
    print("Collection Summary")
    print("="*60)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Show output samples
    print("\n" + "="*60)
    print("Sample Output")
    print("="*60)
    
    stdout_file = test_dir / "stdout.log"
    if stdout_file.exists():
        print("\nstdout.log (first 10 lines):")
        with open(stdout_file) as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                print(f"  {line.rstrip()}")
    
    jsonl_file = test_dir / "aggregated.jsonl"
    if jsonl_file.exists():
        print("\naggregated.jsonl (first 5 lines):")
        with open(jsonl_file) as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                print(f"  {line.rstrip()}")
    
    print("\n" + "="*60)
    print("✓ Test completed successfully!")
    print(f"✓ Output files in: {test_dir}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())