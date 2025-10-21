import time
import csv
import psutil
import subprocess
from datetime import datetime
import json

"""
System resource monitor for GPU, CPU, and RAM metrics.
Supports CSV and JSON export, then some simple error logging, and some configurable options.
"""

class Monitor:

    def __init__(self, output_file, interval, log_console, export_json,
                 metrics, max_duration=None):
        """
        Initialize the monitor.
        :param output_file: CSV file to store metrics
        :param interval: Sampling interval in seconds
        :param log_console: Print metrics to console if True
        :param export_json: Also export metrics to a JSON file
        :param metrics: Tuple of metrics to monitor ("gpu", "cpu", "ram")
        :param max_duration: Maximum monitoring duration in seconds (None = unlimited)
        """
        self.output_file = output_file
        self.interval = interval
        self.log_console = log_console
        self.export_json = export_json
        self.metrics = metrics
        self.max_duration = max_duration  # in seconds
        self.gpu_count = self._get_gpu_count() if "gpu" in metrics else 0
        self._init_csv()
        if self.export_json:
            self._init_json()

    def _init_csv(self):
        """
        Initialize the CSV file and write the header row based on selected metrics.
        """
        with open(self.output_file, mode='w', newline='') as f:
            writer = csv.writer(f)
            header = ["timestamp"]
            if "gpu" in self.metrics:
                for i in range(self.gpu_count):
                    header += [f"gpu{i}_util", f"gpu{i}_mem_used"]
            if "cpu" in self.metrics:
                header += ["cpu_percent"]
            if "ram" in self.metrics:
                header += ["ram_used_MB"]
            writer.writerow(header)

    def _init_json(self):
        """
        Initialize the JSON file (write opening bracket for array).
        """
        with open(self.output_file.replace(".csv", ".json"), mode='w') as f:
            f.write("[")  # inizio array JSON

    def _get_gpu_count(self):
        """
        Detect the number of available GPUs using nvidia-smi.
        :return: Number of GPUs (int)
        """
        try:
            output = subprocess.check_output([
                "nvidia-smi", "--query-gpu=name", "--format=csv,noheader"
            ], encoding="utf-8")
            return len(output.strip().splitlines())
        except Exception as e:
            print(f"GPU count error: {e}")
            return 0

    def _get_gpu_metrics(self):
        """
        Get GPU utilization and memory usage for each GPU.
        :return: List of metrics [util, mem, util, mem, ...]
        """
        metrics = []
        if self.gpu_count == 0:
            return ["N/A", "N/A"] * 1
        try:
            output = subprocess.check_output([
                "nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits"
            ], encoding="utf-8")
            for line in output.strip().splitlines():
                util, mem = line.split(", ")
                metrics += [util, mem]
        except Exception as e:
            print(f"GPU metrics error: {e}")
            metrics = ["N/A", "N/A"] * self.gpu_count
        return metrics

    def _get_cpu_metric(self):
        """
        Get CPU usage percentage.
        :return: CPU percent (float)
        """
        try:
            return psutil.cpu_percent(interval=None)
        except Exception as e:
            print(f"CPU metric error: {e}")
            return "N/A"

    def _get_ram_metric(self):
        """
        Get RAM usage in MB.
        :return: RAM used (int)
        """
        try:
            return int(psutil.virtual_memory().used / (1024 * 1024))  # MB
        except Exception as e:
            print(f"RAM metric error: {e}")
            return "N/A"


    def _write_json(self, data, first):
        """
        Write a single metric entry to the JSON file.
        :param data: Dictionary of metrics
        :param first: True if first entry (no comma)
        """
        json_file = self.output_file.replace(".csv", ".json")
        with open(json_file, mode='a') as f:
            if not first:
                f.write(",\n")
            json.dump(data, f)

    def run(self):
        """
        Start the monitoring loop. Collect metrics at each interval and write to CSV/JSON.
        Stops on Ctrl+C or when max_duration is reached.
        """
        print(f"Monitoring started. Output: {self.output_file}. Press Ctrl+C to stop.")
        start_time = time.time()
        first_json = True
        try:
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [timestamp]
                data = {"timestamp": timestamp}
                if "gpu" in self.metrics:
                    gpu_metrics = self._get_gpu_metrics()
                    row += gpu_metrics
                    for i in range(self.gpu_count):
                        data[f"gpu{i}_util"] = gpu_metrics[i*2]
                        data[f"gpu{i}_mem_used"] = gpu_metrics[i*2+1]
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
                time.sleep(self.interval)
                if self.max_duration and (time.time() - start_time) > self.max_duration:
                    print(f"\nMax monitoring duration reached ({self.max_duration}s). Stopping.")
                    break
        except KeyboardInterrupt:
            print(f"\nMonitoring stopped. Metrics saved in {self.output_file}")
        finally:
            if self.export_json:
                with open(self.output_file.replace(".csv", ".json"), mode='a') as f:
                    f.write("]\n")  # chiusura array JSON


# Example usage:
if __name__ == "__main__":
    # Create a monitor instance with default parameters
    # If run on a system without GPUs, it will still work for CPU and RAM (macOS, etc.)
    monitor = Monitor(
        output_file="metrics.csv",
        interval=1,
        log_console=True,
        export_json=True,
        metrics=("gpu", "cpu", "ram"),
        max_duration=60  # 1 minute
    )
    monitor.run()
