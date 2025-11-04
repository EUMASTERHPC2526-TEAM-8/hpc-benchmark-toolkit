#This is a simple Prometheus client example for testing purposes, to evidentiate in the GRAFANA dashboard the metrics.

from prometheus_client import start_http_server, Gauge
import psutil, time, random

cpu_gauge = Gauge('cpu_usage_percent', 'Simulated CPU usage')
ram_gauge = Gauge('ram_used_megabytes', 'RAM used in MB')

start_http_server(9100)

while True:
    cpu = random.randint(0, 100)
    ram = psutil.virtual_memory().used // (1024*1024)
    cpu_gauge.set(cpu)
    ram_gauge.set(ram)
    time.sleep(1)