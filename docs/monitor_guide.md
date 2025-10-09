# Monitor Module Guide

## Overview
The Monitor module is responsible for collecting **real-time metrics** of the HPC nodes while the benchmark is running. This includes GPU usage, CPU usage, RAM usage, and timestamps for each measurement. The data is saved to a CSV file and can be used for analysis, visualization, or report generation.

---

## Features
- Continuous monitoring during benchmark execution
- Captures GPU utilization and memory usage
- Captures CPU percentage and RAM usage
- Saves metrics in CSV format
- Simple Python script that can be integrated into the workflow

---

## Requirements
- Python 3.x
- `psutil` Python library
- NVIDIA GPU drivers and `nvidia-smi` (if GPUs are present)

Install `psutil` (if not already installed):
```bash
module load Python/3.11.2   # Load Python module if required
pip install --user psutil

---

## How to launch
- cd ~/hpc-benchmark-toolkit/src/monitor
- python3 monitor.py (only after server and client modules are loaded)
- Press Ctrl+C once the benchmark test is finished.
- less metrics.csv (to read all collected metrics)

## Workflow diagram
[User submits recipe]
        │
        ▼
[Interface validates the recipe]
        │
        ▼
[Server Module] ──────────► [Clients Module]
        │                        │
        └────────────► [Monitor.py collects metrics]
                                │
                                ▼
                           [Logs and CSV]
                                │
                                ▼
                            [Final Report]
