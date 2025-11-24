"""
Tailer-based log collector implementation.

Simple Python-based log collector that tails log files from containers
and aggregates them into centralized output files.
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from src.benchmark.logging.base_log_collector import BaseLogCollector, LogSource


class TailerLogCollector(BaseLogCollector):
    """
    Simple log collector that tails log files and aggregates them.
    
    This implementation:
    1. Monitors log files from containers (stdout/stderr)
    2. Writes aggregated logs to central files
    3. Optionally creates structured .jsonl output
    
    It runs in the background using Python threads.
    """
    
    def __init__(self, config: Dict[str, Any], output_dir: Path):
        super().__init__(config, output_dir)
        
        # Configuration
        self.flush_interval = config.get("flush_interval", 5)
        self.create_jsonl = config.get("create_jsonl", True)
        
        # Output file paths
        outputs = config.get("outputs", {})
        self.stdout_file = output_dir / outputs.get("stdout", "stdout.log")
        self.stderr_file = output_dir / outputs.get("stderr", "stderr.log")
        self.jsonl_file = output_dir / outputs.get("aggregated", "aggregated.jsonl")
        
        # Internal state
        self.sources = []
        self.tailer_threads = []
        self.stop_event = threading.Event()
        
        # File handles
        self.stdout_handle = None
        self.stderr_handle = None
        self.jsonl_handle = None
    
    def deploy(self, sources: List[LogSource]) -> bool:
        """Deploy log collection infrastructure."""
        print(f"Deploying tailer log collector for {len(sources)} sources")
        
        try:
            self.sources = sources
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            self.stdout_handle = open(self.stdout_file, 'w', buffering=1)
            self.stderr_handle = open(self.stderr_file, 'w', buffering=1)
            
            if self.create_jsonl:
                self.jsonl_handle = open(self.jsonl_file, 'w', buffering=1)
            
            print(f"Log collector deployed successfully")
            print(f"  - stdout: {self.stdout_file}")
            print(f"  - stderr: {self.stderr_file}")
            if self.create_jsonl:
                print(f"  - jsonl: {self.jsonl_file}")
            
            return True
            
        except Exception as e:
            print(f"Failed to deploy log collector: {e}")
            return False
    
    def start_collection(self) -> bool:
        """Start collecting logs from all sources."""
        print("Starting log collection...")
        
        try:
            self.running = True
            self.stop_event.clear()
            
            for source in self.sources:
                log_file = self._get_log_file_for_source(source)
                
                thread = threading.Thread(
                    target=self._tail_log_file,
                    args=(source, log_file),
                    daemon=True
                )
                thread.start()
                self.tailer_threads.append(thread)
                
                print(f"Started tailer for {source.component} on {source.node}")
            
            # Create loggers_ready flag
            ready_file = self.output_dir / "loggers_ready"
            ready_file.touch()
            print(f"Created loggers_ready flag: {ready_file}")
            
            return True
            
        except Exception as e:
            print(f"Failed to start log collection: {e}")
            self.running = False
            return False
    
    def _get_log_file_for_source(self, source: LogSource) -> Path:
        """Determine the log file path for a given source."""
        if source.component == "server":
            return self.output_dir / f"container_{source.node}.log"
        elif source.component == "client":
            return self.output_dir / f"client_{source.node}.log"
        else:
            raise ValueError(f"Unknown component type: {source.component}")
    
    def _tail_log_file(self, source: LogSource, log_file: Path):
        """Tail a log file and write to aggregated outputs."""
        print(f"Starting tail for {log_file}")
        
        # Wait for file to exist
        while not log_file.exists() and not self.stop_event.is_set():
            time.sleep(1)
        
        if self.stop_event.is_set():
            return
        
        try:
            with open(log_file, 'r') as f:
                while not self.stop_event.is_set():
                    line = f.readline()
                    
                    if line:
                        self._process_log_line(source, line.rstrip('\n'))
                    else:
                        time.sleep(0.1)
                        
        except Exception as e:
            print(f"Error tailing {log_file}: {e}")
    
    def _process_log_line(self, source: LogSource, line: str):
        """Process a single log line from a source."""
        try:
            timestamp = datetime.utcnow().isoformat() + 'Z'
            
            # Write to aggregated stdout with metadata
            log_entry = f"[{timestamp}] [{source.node}] [{source.component}] {line}\n"
            self.stdout_handle.write(log_entry)
            
            # Write to structured .jsonl
            if self.create_jsonl and self.jsonl_handle:
                jsonl_entry = {
                    "timestamp": timestamp,
                    "node": source.node,
                    "component": source.component,
                    "message": line
                }
                self.jsonl_handle.write(json.dumps(jsonl_entry) + '\n')
                
        except Exception as e:
            print(f"Error processing log line: {e}")
    
    def is_ready(self) -> bool:
        """Check if log collector is ready."""
        ready_file = self.output_dir / "loggers_ready"
        return ready_file.exists()
    
    def stop_collection(self) -> Dict[str, Any]:
        """Stop log collection and finalize."""
        print("Stopping log collection...")
        
        try:
            self.stop_event.set()
            self.running = False
            
            for thread in self.tailer_threads:
                thread.join(timeout=5)
            
            if self.stdout_handle:
                self.stdout_handle.close()
            if self.stderr_handle:
                self.stderr_handle.close()
            if self.jsonl_handle:
                self.jsonl_handle.close()
            
            summary = {
                "stdout_lines": self._count_lines(self.stdout_file),
                "stderr_lines": self._count_lines(self.stderr_file),
                "files_created": [
                    str(self.stdout_file),
                    str(self.stderr_file)
                ]
            }
            
            if self.create_jsonl:
                summary["jsonl_lines"] = self._count_lines(self.jsonl_file)
                summary["files_created"].append(str(self.jsonl_file))
            
            print(f"Log collection stopped. Summary: {summary}")
            return summary
            
        except Exception as e:
            print(f"Error stopping log collection: {e}")
            return {"error": str(e)}
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        try:
            with open(file_path, 'r') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    @classmethod
    def parse_collector_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tailer-specific configuration from recipe.
        
        Args:
            recipe_config: Full recipe configuration
            
        Returns:
            Dict containing tailer configuration
            
        Raises:
            ValueError: If required configuration is missing
        """
        logging_config = recipe_config.get("logging", {})
        
        if not logging_config:
            raise ValueError("Recipe must include 'logging' section")
        
        # Validate collector type
        collector_type = logging_config.get("type", "tailer")
        if collector_type != "tailer":
            raise ValueError(f"Invalid collector type for TailerLogCollector: {collector_type}")
        
        # Build config with defaults
        config = {
            "type": "tailer",
            "create_jsonl": logging_config.get("create_jsonl", True),
            "flush_interval": logging_config.get("flush_interval", 5),
            "outputs": logging_config.get("outputs", {
                "stdout": "stdout.log",
                "stderr": "stderr.log",
                "aggregated": "aggregated.jsonl"
            })
        }
        
        return config