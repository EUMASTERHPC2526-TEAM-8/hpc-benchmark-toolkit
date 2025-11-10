#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import time
from datetime import datetime

import psutil
from prometheus_client import Gauge, Counter, Summary, start_http_server, REGISTRY, CollectorRegistry, generate_latest


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
        except Exception:
            pass

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

# ----------------------------
# Prometheus metrics
# ----------------------------
CPU_USAGE = Gauge("cpu_usage_percent", "CPU usage percentage")
RAM_USED_MB = Gauge("ram_used_megabytes", "RAM used in MB")
DISK_USAGE_PERCENT = Gauge("disk_usage_percent", "Root filesystem usage percentage")

# New metrics
PROC_COUNT = Gauge("process_count", "Number of running processes")
UPTIME_SECONDS = Gauge("system_uptime_seconds", "System uptime in seconds")

NET_BYTES_SENT_PER_S = Gauge("net_bytes_sent_per_second", "Network bytes sent per second")
NET_BYTES_RECV_PER_S = Gauge("net_bytes_recv_per_second", "Network bytes received per second")

DISK_READ_BYTES_PER_S = Gauge("disk_read_bytes_per_second", "Disk read bytes per second")
DISK_WRITE_BYTES_PER_S = Gauge("disk_write_bytes_per_second", "Disk write bytes per second")

GPU_UTIL = Gauge("gpu_utilization_percent", "GPU utilization percentage")
GPU_MEM_MB = Gauge("gpu_memory_used_megabytes", "GPU memory used in MB")

SAMPLES_TOTAL = Counter("monitor_samples_total", "Total number of samples collected by the monitor")
LOOP_DURATION = Summary("monitor_loop_duration_seconds", "Duration of each monitoring loop iteration (seconds)")

# ----------------------------
# Helpers
# ----------------------------
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def has_nvidia_smi() -> bool:
    return shutil.which("nvidia-smi") is not None

def read_gpu_metrics():
    """
    Returns (gpu_util_percent, gpu_mem_used_mb) or (None, None) if unavailable.
    """
    if not has_nvidia_smi():
        return None, None
    try:
        # query first GPU (idx 0). If multiple GPUs, you can loop over them and sum/avg.
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used",
            "--format=csv,noheader,nounits"
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        # If multiple GPUs, out has multiple lines; here we take the first
        line = out.splitlines()[0]
        util_str, mem_str = [x.strip() for x in line.split(",")]
        util = float(util_str) if util_str else None
        mem_mb = float(mem_str) if mem_str else None
        return util, mem_mb
    except Exception:
        return None, None

def jsonl_append(path: str, record: dict):
    with open(path, "a") as f:
        json.dump(record, f)
        f.write("\n")

def csv_append(path: str, header: list, row: dict):
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            w.writeheader()
        w.writerow(row)

# ----------------------------
# Core sampling function
# ----------------------------
def sample_metrics(prev_state):
    """
    prev_state: dict holding previous counters & timestamp for rate calculations.
    returns: (metrics_dict, new_state)
    """
    ts = time.time()

    cpu = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    ram_used_mb = vm.used / (1024 * 1024)

    # disk usage (root fs)
    try:
        disk_usage_percent = psutil.disk_usage("/").percent
    except Exception:
        disk_usage_percent = None

    # process count
    try:
        proc_count = sum(1 for _ in psutil.process_iter(attrs=()))
    except Exception:
        proc_count = None

    # uptime
    uptime = max(0.0, ts - psutil.boot_time())

    # network rates via deltas
    net = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()

    net_bytes_sent_ps = None
    net_bytes_recv_ps = None
    disk_read_ps = None
    disk_write_ps = None

    if prev_state and "ts" in prev_state:
        dt = ts - prev_state["ts"]
        if dt > 0:
            if prev_state.get("net"):
                net_bytes_sent_ps = max(0.0, (net.bytes_sent - prev_state["net"].bytes_sent) / dt)
                net_bytes_recv_ps = max(0.0, (net.bytes_recv - prev_state["net"].bytes_recv) / dt)
            if prev_state.get("disk_io"):
                disk_read_ps = max(0.0, (disk_io.read_bytes - prev_state["disk_io"].read_bytes) / dt)
                disk_write_ps = max(0.0, (disk_io.write_bytes - prev_state["disk_io"].write_bytes) / dt)

    # GPU
    gpu_util, gpu_mem_mb = read_gpu_metrics()

    metrics = {
        "timestamp": ts,
        "iso_time": datetime.utcfromtimestamp(ts).isoformat() + "Z",
        "cpu_usage_percent": cpu,
        "ram_used_megabytes": ram_used_mb,
        "disk_usage_percent": disk_usage_percent,
        "process_count": proc_count,
        "system_uptime_seconds": uptime,
        "net_bytes_sent_per_second": net_bytes_sent_ps,
        "net_bytes_recv_per_second": net_bytes_recv_ps,
        "disk_read_bytes_per_second": disk_read_ps,
        "disk_write_bytes_per_second": disk_write_ps,
        "gpu_utilization_percent": gpu_util,
        "gpu_memory_used_megabytes": gpu_mem_mb,
    }

    new_state = {
        "ts": ts,
        "net": net,
        "disk_io": disk_io,
    }
    return metrics, new_state

def update_prometheus(metrics: dict):
    if metrics["cpu_usage_percent"] is not None:
        CPU_USAGE.set(metrics["cpu_usage_percent"])
    if metrics["ram_used_megabytes"] is not None:
        RAM_USED_MB.set(metrics["ram_used_megabytes"])
    if metrics["disk_usage_percent"] is not None:
        DISK_USAGE_PERCENT.set(metrics["disk_usage_percent"])
    if metrics["process_count"] is not None:
        PROC_COUNT.set(metrics["process_count"])
    if metrics["system_uptime_seconds"] is not None:
        UPTIME_SECONDS.set(metrics["system_uptime_seconds"])

    if metrics["net_bytes_sent_per_second"] is not None:
        NET_BYTES_SENT_PER_S.set(metrics["net_bytes_sent_per_second"])
    if metrics["net_bytes_recv_per_second"] is not None:
        NET_BYTES_RECV_PER_S.set(metrics["net_bytes_recv_per_second"])

    if metrics["disk_read_bytes_per_second"] is not None:
        DISK_READ_BYTES_PER_S.set(metrics["disk_read_bytes_per_second"])
    if metrics["disk_write_bytes_per_second"] is not None:
        DISK_WRITE_BYTES_PER_S.set(metrics["disk_write_bytes_per_second"])

    if metrics["gpu_utilization_percent"] is not None:
        GPU_UTIL.set(metrics["gpu_utilization_percent"])
    if metrics["gpu_memory_used_megabytes"] is not None:
        GPU_MEM_MB.set(metrics["gpu_memory_used_megabytes"])

# ----------------------------
# Runner
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Prometheus system monitor")
    parser.add_argument("--port", type=int, default=9100, help="Prometheus exporter port")
    parser.add_argument("--addr", type=str, default="0.0.0.0", help="Exporter bind address")
    parser.add_argument("--interval", type=float, default=5.0, help="Sampling interval (seconds)")
    parser.add_argument("--max_duration", type=float, default=0.0, help="Stop after N seconds (0 = run forever)")

    parser.add_argument("--log_console", type=lambda x: str(x).lower() == "true", default=False,
                        help="Print metrics to console")
    parser.add_argument("--export_json", type=lambda x: str(x).lower() == "true", default=True,
                        help="Append JSON lines to file")
    parser.add_argument("--export_csv", type=lambda x: str(x).lower() == "true", default=True,
                        help="Append CSV rows to file")
    parser.add_argument("--output_dir", type=str, default="./monitor_output",
                        help="Directory for JSON/CSV outputs (relative to current working dir)")

    args = parser.parse_args()

    ensure_dir(args.output_dir)
    json_path = os.path.join(args.output_dir, "metrics.jsonl")
    csv_path = os.path.join(args.output_dir, "metrics.csv")

    # Start exporter
    start_http_server(args.port, addr=args.addr)
    # quiet by default; only initial info line
    print(f"Prometheus exporter started at http://{args.addr}:{args.port}")

    csv_header = [
        "timestamp",
        "iso_time",
        "cpu_usage_percent",
        "ram_used_megabytes",
        "disk_usage_percent",
        "process_count",
        "system_uptime_seconds",
        "net_bytes_sent_per_second",
        "net_bytes_recv_per_second",
        "disk_read_bytes_per_second",
        "disk_write_bytes_per_second",
        "gpu_utilization_percent",
        "gpu_memory_used_megabytes",
    ]

    prev_state = {}
    start_ts = time.time()

    while True:
        with LOOP_DURATION.time():
            metrics, prev_state = sample_metrics(prev_state)
            update_prometheus(metrics)
            SAMPLES_TOTAL.inc()

        if args.log_console:
            print(json.dumps(metrics, indent=2))

        if args.export_json:
            jsonl_append(json_path, metrics)

        if args.export_csv:
            csv_append(csv_path, csv_header, metrics)

        if args.max_duration and (time.time() - start_ts) >= args.max_duration:
            break

        time.sleep(args.interval)

if __name__ == "__main__":
    main()

