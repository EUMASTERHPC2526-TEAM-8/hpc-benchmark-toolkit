#!/usr/bin/env python3
"""
Local test for logging system without HPC.
Tests TailerLogCollector in isolation.
"""

import os
import time
import tempfile
from pathlib import Path
from benchmark.logging.tailer_log_collector import TailerLogCollector
from benchmark.logging.base_log_collector import LogSource

def test_basic_logging():
    """Test basic log collection."""
    print("="*70)
    print("TEST: Basic Log Collection")
    print("="*70)
    
    # Create temporary directories
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "logs"
        source_dir = tmpdir / "sources"
        output_dir.mkdir()
        source_dir.mkdir()
        
        # Create fake log files (simulating container logs)
        server_log = source_dir / "container_node001.log"
        client_log = source_dir / "client_node002.log"
        
        server_log.write_text("")  # Start empty
        client_log.write_text("")
        
        # Configure log collector
        config = {
            "type": "tailer",
            "create_jsonl": True,
            "flush_interval": 1,
            "outputs": {
                "stdout": "stdout.log",
                "stderr": "stderr.log",
                "aggregated": "aggregated.jsonl"
            }
        }
        
        # Create log sources
        sources = [
            LogSource(node="node001", component="server", container_name="ollama_server"),
            LogSource(node="node002", component="client", container_name="client_1")
        ]
        
        # Override _get_log_file_for_source to use our temp files
        collector = TailerLogCollector(config, output_dir)
        collector._get_log_file_for_source = lambda source: (
            server_log if source.component == "server" else client_log
        )
        
        # Deploy and start collection
        print("\n[1] Deploying log collector...")
        assert collector.deploy(sources), "Deployment failed"
        print("✓ Deployed")
        
        print("\n[2] Starting log collection...")
        assert collector.start_collection(), "Start failed"
        print("✓ Started")
        
        # Wait for logger ready flag
        time.sleep(2)
        assert collector.is_ready(), "Collector not ready"
        print("✓ Collector ready")
        
        # Simulate container logs being written
        print("\n[3] Simulating log generation...")
        for i in range(5):
            server_log.write_text(
                server_log.read_text() + f"[Server] Log message {i}\n"
            )
            client_log.write_text(
                client_log.read_text() + f"[Client] Request {i} completed\n"
            )
            time.sleep(0.5)
        
        print("✓ Generated 10 log lines")
        
        # Give collector time to process
        time.sleep(3)
        
        # Stop collection
        print("\n[4] Stopping log collection...")
        summary = collector.stop_collection()
        print(f"✓ Stopped. Summary: {summary}")
        
        # Verify outputs
        print("\n[5] Verifying outputs...")
        stdout_file = output_dir / "stdout.log"
        jsonl_file = output_dir / "aggregated.jsonl"
        
        assert stdout_file.exists(), "stdout.log not created"
        assert jsonl_file.exists(), "aggregated.jsonl not created"
        
        # Check content
        stdout_content = stdout_file.read_text()
        jsonl_content = jsonl_file.read_text()
        
        print(f"  - stdout.log: {len(stdout_content.splitlines())} lines")
        print(f"  - aggregated.jsonl: {len(jsonl_content.splitlines())} lines")
        
        assert "Server" in stdout_content, "Server logs missing"
        assert "Client" in stdout_content, "Client logs missing"
        assert "node001" in stdout_content, "Node labels missing"
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
        # Print sample output
        print("\nSample stdout.log:")
        print("-" * 70)
        print("\n".join(stdout_content.splitlines()[:5]))
        print("...")
        
        print("\nSample aggregated.jsonl:")
        print("-" * 70)
        print("\n".join(jsonl_content.splitlines()[:2]))
        print("...")

if __name__ == "__main__":
    test_basic_logging()