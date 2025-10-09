import time
import csv
import psutil
import subprocess
from datetime import datetime

output_file = "metrics.csv"

with open(output_file, mode='w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "gpu_util", "gpu_mem_used", "cpu_percent", "ram_used_MB"])

print("Monitoring started. Press Ctrl+C to stop.")

try:
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # (1 GPU assumption, do cylce for more gpu)
        try:
            gpu_info = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                 "--format=csv,noheader,nounits"], encoding="utf-8"
            ).strip().split(", ")
            gpu_util = gpu_info[0]
            gpu_mem_used = gpu_info[1]
        except Exception:
            gpu_util = "N/A"
            gpu_mem_used = "N/A"

        # CPU e RAM
        cpu_percent = psutil.cpu_percent(interval=1)
        ram_used = int(psutil.virtual_memory().used / (1024 * 1024))  # MB

        # Monitor data on CSV
        with open(output_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, gpu_util, gpu_mem_used, cpu_percent, ram_used])

        time.sleep(1)  # intervallo di 1 secondo tra le misurazioni

except KeyboardInterrupt:
    print("\nMonitoring stopped. Metrics saved in", output_file)
