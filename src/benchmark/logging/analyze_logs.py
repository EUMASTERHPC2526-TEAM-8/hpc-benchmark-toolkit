#!/usr/bin/env python3
"""
Benchmark Log Analyzer
Analyzes aggregated.jsonl logs from HPC benchmark runs
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Any
import statistics


class BenchmarkLogAnalyzer:
    def __init__(self, jsonl_file: str)-> None:
        self.jsonl_file = Path(jsonl_file)
        self.logs = []
        self.load_logs()
        
    def load_logs(self)-> None:
        """Load all log entries from JSONL file"""
        if not self.jsonl_file.exists():
            print(f"Error: File not found: {self.jsonl_file}")
            sys.exit(1)
            
        with open(self.jsonl_file) as f:
            for line in f:
                try:
                    self.logs.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON line: {e}")
        
        print(f"Loaded {len(self.logs)} log entries\n")
    
    def get_time_range(self) -> tuple:
        """Get start and end timestamps"""
        if not self.logs:
            return None, None
        
        timestamps = [datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')) 
                     for log in self.logs]
        return min(timestamps), max(timestamps)
    
    def analyze_components(self) -> Dict[str, int]:
        """Count logs per component"""
        return Counter(log['component'] for log in self.logs)
    
    def analyze_nodes(self) -> Dict[str, int]:
        """Count logs per node"""
        return Counter(log['node'] for log in self.logs)
    
    def extract_latencies(self) -> List[float]:
        """Extract request latencies from server logs"""
        latencies = []
        pattern = r'(\d+\.\d+)s'
        
        for log in self.logs:
            if log['component'] == 'server' and 'POST' in log['message'] and '/api/generate' in log['message']:
                match = re.search(pattern, log['message'])
                if match:
                    latencies.append(float(match.group(1)))
        
        return latencies
    
    def extract_benchmark_results(self) -> Dict[str, Any]:
        """Extract benchmark completion statistics"""
        results = {
            'threads': [],
            'total_requests': 0,
            'total_errors': 0
        }
        
        pattern = r'\[Thread (\d+)\] Benchmark complete: (\d+) requests, (\d+) errors'
        
        for log in self.logs:
            if 'Benchmark complete' in log['message']:
                match = re.search(pattern, log['message'])
                if match:
                    thread_id = int(match.group(1))
                    requests = int(match.group(2))
                    errors = int(match.group(3))
                    
                    results['threads'].append({
                        'thread_id': thread_id,
                        'requests': requests,
                        'errors': errors
                    })
                    results['total_requests'] += requests
                    results['total_errors'] += errors
        
        return results
    
    def find_errors(self) -> List[Dict[str, Any]]:
        """Find all error messages"""
        errors = []
        error_keywords = ['error', 'failed', 'exception', 'traceback', 'fatal']
        
        for log in self.logs:
            msg_lower = log['message'].lower()
            if any(keyword in msg_lower for keyword in error_keywords):
                errors.append(log)
        
        return errors
    
    def analyze_timeline(self, interval_seconds: int = 10) -> Dict[str, List[int]]:
        """Group logs by time intervals"""
        if not self.logs:
            return {}
        
        start_time, end_time = self.get_time_range()
        duration = (end_time - start_time).total_seconds()
        
        intervals = defaultdict(lambda: {'server': 0, 'client': 0})
        
        for log in self.logs:
            timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
            elapsed = (timestamp - start_time).total_seconds()
            interval_num = int(elapsed / interval_seconds)
            intervals[interval_num][log['component']] += 1
        
        return dict(intervals)
    
    def generate_report(self):
        """Generate comprehensive analysis report"""
        print("=" * 80)
        print("BENCHMARK LOG ANALYSIS REPORT")
        print("=" * 80)
        print()
        
        # Time range
        start_time, end_time = self.get_time_range()
        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            print(f"   Time Range:")
            print(f"   Start: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   End:   {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            print()
        
        # Component breakdown
        components = self.analyze_components()
        print(f" Log Distribution:")
        for component, count in components.items():
            print(f"   {component}: {count} logs")
        print()
        
        # Node breakdown
        nodes = self.analyze_nodes()
        print(f" Node Distribution:")
        for node, count in nodes.items():
            print(f"   {node}: {count} logs")
        print()
        
        # Latency analysis
        latencies = self.extract_latencies()
        if latencies:
            print(f" Request Latency Analysis:")
            print(f"   Total requests: {len(latencies)}")
            print(f"   Average: {statistics.mean(latencies):.3f}s")
            print(f"   Median:  {statistics.median(latencies):.3f}s")
            print(f"   Min:     {min(latencies):.3f}s")
            print(f"   Max:     {max(latencies):.3f}s")
            if len(latencies) > 1:
                print(f"   StdDev:  {statistics.stdev(latencies):.3f}s")
            
            # Percentiles
            sorted_lat = sorted(latencies)
            p50 = sorted_lat[len(sorted_lat) * 50 // 100]
            p90 = sorted_lat[len(sorted_lat) * 90 // 100]
            p95 = sorted_lat[len(sorted_lat) * 95 // 100]
            p99 = sorted_lat[len(sorted_lat) * 99 // 100]
            
            print(f"\n   Percentiles:")
            print(f"   P50: {p50:.3f}s")
            print(f"   P90: {p90:.3f}s")
            print(f"   P95: {p95:.3f}s")
            print(f"   P99: {p99:.3f}s")
            print()
        
        # Benchmark results
        results = self.extract_benchmark_results()
        if results['threads']:
            print(f" Benchmark Results:")
            print(f"   Threads: {len(results['threads'])}")
            print(f"   Total requests: {results['total_requests']}")
            print(f"   Total errors: {results['total_errors']}")
            print()
            
            print(f"   Per-thread breakdown:")
            for thread in sorted(results['threads'], key=lambda x: x['thread_id']):
                print(f"   - Thread {thread['thread_id']}: {thread['requests']} requests, {thread['errors']} errors")
            
            if start_time and end_time and duration > 0:
                throughput = results['total_requests'] / duration
                print(f"\n   Throughput: {throughput:.3f} requests/second")
            print()
        
        # Error analysis
        errors = self.find_errors()
        if errors:
            print(f" Errors Found: {len(errors)}")
            print(f"   First 5 errors:")
            for error in errors[:5]:
                print(f"   [{error['timestamp']}] [{error['node']}] {error['message'][:100]}")
            print()
        else:
            print(f"No errors found!")
            print()
        
        # Timeline analysis
        print(f" Activity Timeline (10-second intervals):")
        timeline = self.analyze_timeline(interval_seconds=10)
        if timeline:
            for interval_num in sorted(timeline.keys())[:10]:  # Show first 10 intervals
                data = timeline[interval_num]
                time_mark = interval_num * 10
                print(f"   {time_mark:4d}s: server={data['server']:3d}, client={data['client']:3d}")
            if len(timeline) > 10:
                print(f"   ... ({len(timeline) - 10} more intervals)")
            print()
        
        print("=" * 80)
    
    def export_csv(self, output_file: str = "latencies.csv"):
        """Export latencies to CSV for further analysis"""
        latencies = self.extract_latencies()
        if not latencies:
            print("No latencies to export")
            return
        
        with open(output_file, 'w') as f:
            f.write("request_num,latency_seconds\n")
            for i, lat in enumerate(latencies, 1):
                f.write(f"{i},{lat}\n")
        
        print(f"Exported {len(latencies)} latencies to {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_logs.py <aggregated.jsonl> [--export-csv]")
        print("\nExample:")
        print("  python analyze_logs.py aggregated.jsonl")
        print("  python analyze_logs.py experiments/test-logging-final_20251221_234115/aggregated.jsonl --export-csv")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    export_csv = "--export-csv" in sys.argv
    
    analyzer = BenchmarkLogAnalyzer(jsonl_file)
    analyzer.generate_report()
    
    if export_csv:
        analyzer.export_csv()


if __name__ == "__main__":
    main()