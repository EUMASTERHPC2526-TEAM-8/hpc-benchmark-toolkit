#!/usr/bin/env python3
"""
Avvio semplice del Monitor locale che push-a verso il Pushgateway del docker-compose.
Usa per un test rapido con la guida del README principale.
"""
from monitor import Monitor
import os
import time
import requests

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://localhost:9093")
JOB = os.getenv("PROM_JOB", "local-test")
INSTANCE = os.getenv("PROM_INSTANCE", "dev-node")

if __name__ == "__main__":
    # Wait until Pushgateway is ready
    url = f"{PUSHGATEWAY_URL.rstrip('/')}/metrics"
    timeout = int(os.getenv("WAIT_TIMEOUT", "40"))
    t0 = time.time()
    print(f"Attendo Pushgateway: {url} (timeout {timeout}s)...")
    while True:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print("Pushgateway pronto ✓")
                break
        except Exception:
            pass
        if time.time() - t0 > timeout:
            print("Warning: Pushgateway non pronto, procedo comunque…")
            break
        time.sleep(2)
    m = Monitor(
        output_file="local_metrics.csv",
        interval=5,
        log_console=True,
        export_json=False,
        metrics=("cpu","ram","gpu"),
        max_duration=int(os.getenv("MONITOR_DURATION", "120")),
        prometheus_pushgateway_url=PUSHGATEWAY_URL,
        prometheus_grouping_labels={"job": JOB, "instance": INSTANCE},
    )
    print(f"Pushgateway: {PUSHGATEWAY_URL} | job={JOB} instance={INSTANCE}")
    m.run()
