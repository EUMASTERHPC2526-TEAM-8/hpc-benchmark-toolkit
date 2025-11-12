import time
import csv
import psutil
import subprocess
from datetime import datetime
import json
import os
import socket
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    Counter,
    Summary,
    start_http_server,
    push_to_gateway,
)

"""
System resource monitor for GPU, CPU, and RAM metrics.
Supports CSV and JSON export and Prometheus integration (always enabled).
"""


class Monitor:

    def __init__(
        self,
        output_file="metrics.csv",
        interval=1,
        log_console=True,
        export_json=False,
        metrics=("gpu", "cpu", "ram"),
        max_duration=None,
        # Prometheus options
        prometheus_port=9100,
        prometheus_addr="0.0.0.0",
        prometheus_pushgateway_url=None,
        prometheus_grouping_labels=None,
        prometheus_start_http_server=False,
        prometheus_registry=None,
        prometheus_push_interval=15,
    ):
        """
        Initialize the monitor.
        :param output_file: CSV file to store metrics
        :param interval: Sampling interval in seconds
        :param log_console: Print metrics to console if True
        :param export_json: Also export metrics to a JSON file
        :param metrics: Tuple of metrics to monitor ("gpu", "cpu", "ram")
        :param max_duration: Maximum monitoring duration in seconds (None = unlimited)
        :param prometheus_*: Prometheus configuration (always enabled internally)
        """
        self.output_file = output_file
        self.interval = interval
        self.log_console = log_console
        self.export_json = export_json
        self.metrics = metrics
        self.max_duration = max_duration

        # Prometheus configuration
        self.prometheus_port = prometheus_port
        self.prometheus_addr = prometheus_addr
        self.prometheus_pushgateway_url = prometheus_pushgateway_url
        self.prometheus_grouping_labels = prometheus_grouping_labels or {}
        self.prometheus_start_http_server = prometheus_start_http_server
        self.prometheus_registry = prometheus_registry
        self.prometheus_push_interval = prometheus_push_interval
        self._last_prom_push = 0.0

        self.gpu_count = self._get_gpu_count() if "gpu" in metrics else 0
        self._init_csv()
        if self.export_json:
            self._init_json()
        self._init_prometheus()

    def _init_csv(self):
        with open(self.output_file, mode='w', newline='') as f:
            writer = csv.writer(f)
            header = ["timestamp"]
            if "gpu" in self.metrics:
                for i in range(self.gpu_count):
                    header += [f"gpu{i}_util", f"gpu{i}_mem_used"]
            if "cpu" in self.metrics:
                header.append("cpu_percent")
            if "ram" in self.metrics:
                header.append("ram_used_MB")
            writer.writerow(header)

    def _init_json(self):
        with open(self.output_file.replace(".csv", ".json"), mode='w') as f:
            f.write("[")

    def _get_gpu_count(self):
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], encoding="utf-8"
            )
            return len(output.strip().splitlines())
        except Exception:
            return 0

    def _get_gpu_metrics(self):
        metrics = []
        if self.gpu_count == 0:
            return ["N/A", "N/A"] * 1
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                encoding="utf-8",
            )
            for line in output.strip().splitlines():
                util, mem = line.split(", ")
                metrics += [util, mem]
        except Exception:
            metrics = ["N/A", "N/A"] * self.gpu_count
        return metrics

    def _get_cpu_metric(self):
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return "N/A"

    def _get_ram_metric(self):
        try:
            return int(psutil.virtual_memory().used / (1024 * 1024))
        except Exception:
            return "N/A"

    def _init_prometheus(self):
        """Initialize Prometheus metrics, registry, and optional HTTP exporter/pushgateway."""
        hostname = socket.gethostname()
        slurm_job_id = os.environ.get("SLURM_JOB_ID")
        default_labels = {
            "job": "hpc-monitor",
            "instance": hostname,
        }
        if slurm_job_id:
            default_labels["slurm_job_id"] = slurm_job_id
        default_labels.update(self.prometheus_grouping_labels)
        self.prom_labels = default_labels

        # Create or use provided registry
        self.registry = self.prometheus_registry or CollectorRegistry()

        # Core metrics
        self.prom_samples_total = Counter(
            "monitor_samples_total",
            "Total number of samples collected by the monitor",
            registry=self.registry,
        )
        self.prom_loop_seconds = Summary(
            "monitor_loop_duration_seconds",
            "Duration of each monitoring loop iteration (seconds)",
            registry=self.registry,
        )
        # Gauges
        if "cpu" in self.metrics:
            self.prom_cpu_percent = Gauge(
                "cpu_usage_percent",
                "CPU usage percentage",
                registry=self.registry,
            )
        else:
            self.prom_cpu_percent = None
        if "ram" in self.metrics:
            self.prom_ram_used_mb = Gauge(
                "ram_used_megabytes",
                "RAM used in MB",
                registry=self.registry,
            )
        else:
            self.prom_ram_used_mb = None
        if "gpu" in self.metrics:
            self.prom_gpu_util = Gauge(
                "gpu_utilization_percent",
                "GPU utilization percentage",
                ["gpu_id"],
                registry=self.registry,
            )
            self.prom_gpu_mem_mb = Gauge(
                "gpu_memory_used_megabytes",
                "GPU memory used in MB",
                ["gpu_id"],
                registry=self.registry,
            )
        else:
            self.prom_gpu_util = None
            self.prom_gpu_mem_mb = None

        # Start HTTP exporter if requested (pull model)
        if self.prometheus_start_http_server and self.prometheus_port and self.prometheus_addr:
            try:
                start_http_server(self.prometheus_port, addr=self.prometheus_addr, registry=self.registry)
                print(f"Prometheus exporter started at http://{self.prometheus_addr}:{self.prometheus_port}")
            except Exception as e:
                print(f"Failed to start Prometheus exporter: {e}")

    def _update_prometheus(self, data, loop_duration):
        """Update Prometheus metrics for the current sample."""
        # Increment counters and observe durations
        self.prom_samples_total.inc()
        self.prom_loop_seconds.observe(loop_duration)
        
        if self.prom_cpu_percent is not None:
            val = data.get("cpu_percent")
            if isinstance(val, (int, float)):
                self.prom_cpu_percent.set(val)
        if self.prom_ram_used_mb is not None:
            val = data.get("ram_used_MB")
            if isinstance(val, (int, float)):
                self.prom_ram_used_mb.set(val)
        if self.prom_gpu_util is not None and self.prom_gpu_mem_mb is not None:
            for i in range(self.gpu_count):
                util = data.get(f"gpu{i}_util")
                mem = data.get(f"gpu{i}_mem_used")
                try:
                    if util not in (None, "N/A"):
                        self.prom_gpu_util.labels(str(i)).set(float(util))
                    if mem not in (None, "N/A"):
                        self.prom_gpu_mem_mb.labels(str(i)).set(float(mem))
                except Exception:
                    pass

    def _push_prometheus_if_due(self, now):
        """Push metrics to Pushgateway if configured and interval elapsed."""
        if not self.prometheus_pushgateway_url:
            return
        if (now - self._last_prom_push) < self.prometheus_push_interval:
            return
        try:
            push_to_gateway(
                self.prometheus_pushgateway_url,
                job=self.prom_labels.get("job", "hpc-monitor"),
                grouping_key=self.prom_labels,
                registry=self.registry,
            )
            self._last_prom_push = now
            if self.log_console:
                print(f"✅ Pushed metrics to {self.prometheus_pushgateway_url}")
        except Exception as e:
            if self.log_console:
                print(f"❌ Failed to push to Pushgateway: {e}")

    def _write_json(self, data, first):
        json_file = self.output_file.replace(".csv", ".json")
        with open(json_file, mode='a') as f:
            if not first:
                f.write(",\n")
            json.dump(data, f)

    def run(self):
        print(f"Monitoring started. Output: {self.output_file}. Press Ctrl+C to stop.")
        start_time = time.time()
        first_json = True
        try:
            while True:
                loop_start = time.time()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [timestamp]
                data = {"timestamp": timestamp}
                if "gpu" in self.metrics:
                    gpu_metrics = self._get_gpu_metrics()
                    row += gpu_metrics
                    for i in range(self.gpu_count):
                        data[f"gpu{i}_util"] = gpu_metrics[i * 2]
                        data[f"gpu{i}_mem_used"] = gpu_metrics[i * 2 + 1]
                if "cpu" in self.metrics:
                    cpu_percent = self._get_cpu_metric()
                    row.append(cpu_percent)
                    data["cpu_percent"] = cpu_percent
                if "ram" in self.metrics:
                    ram_used = self._get_ram_metric()
                    row.append(ram_used)
                    data["ram_used_MB"] = ram_used
                with open(self.output_file, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                if self.export_json:
                    self._write_json(data, first_json)
                    first_json = False
                if self.log_console:
                    print(row)

                # Update Prometheus metrics
                loop_duration = time.time() - loop_start
                self._update_prometheus(data, loop_duration)
                self._push_prometheus_if_due(time.time())

                time.sleep(self.interval)
                if self.max_duration and (time.time() - start_time) > self.max_duration:
                    print(f"\nMax monitoring duration reached ({self.max_duration}s). Stopping.")
                    break
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Metrics saved in {self.output_file}")
        finally:
            if self.export_json:
                with open(self.output_file.replace(".csv", ".json"), mode='a') as f:
                    f.write("]\n")


# Example usage:
if __name__ == "__main__":
    # If run on a system without GPUs, it will still work for CPU and RAM (macOS, etc.)
    monitor = Monitor(
        output_file="metrics.csv",
        interval=1,
        log_console=True,
        export_json=True,
        metrics=("gpu", "cpu", "ram"),
        max_duration=180, 
        # Prometheus example (exporter): uncomment to enable
        prometheus_start_http_server=True,
        prometheus_port=9100,
        prometheus_addr="0.0.0.0",
        # Pushgateway example: uncomment and set your URL
        # ATTENZIONE: se esegui questo script dal tuo host (non dentro Docker), "pushgateway" NON si risolve.
        # Usa ad esempio:
        #   - http://localhost:9093  (Pushgateway del docker-compose locale)
        #   - http://localhost:9091  (SSH tunnel verso MeluXina)
        #   - http://<nome-nodo>:9091 (direttamente sul nodo HPC)
        prometheus_pushgateway_url=os.getenv("PUSHGATEWAY_URL", "http://localhost:9093"),
        prometheus_grouping_labels={"project": "hpc-benchmark"},
    )
    monitor.run()
