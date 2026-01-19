# HPC Benchmark Toolkit

**Last Updated:** January 2026

Benchmarking LLM inference (Ollama, vLLM) on HPC clusters with live Prometheus/Grafana monitoring. Optimized for MeluXina (Slurm + Apptainer).

## Table of Contents
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Installation & Setup](#3-installation--setup)
4. [Quick Start Guide](#4-quick-start-guide)
5. [CLI Reference](#5-cli-reference)
6. [Recipe Configuration](#6-recipe-configuration)
7. [Monitoring & Metrics](#7-monitoring--metrics)
8. [Distributed Benchmarking](#8-distributed-benchmarking)
9. [Extending the Framework](#9-extending-the-framework)
10. [API Reference](#10-api-reference)
11. [Troubleshooting](#11-troubleshooting)
12. [Best Practices](#12-best-practices)
13. [License](#13-license)
14. [Support](#14-support)

## 1. Overview
- Benchmark and compare Ollama and vLLM on HPC with reproducible YAML recipes.
- Real-time metrics via Prometheus/Grafana (Pushgateway), ready-made dashboards.
- Built for MeluXina (Slurm + Apptainer); usable locally with venv/Docker.

## 2. Architecture
- Orchestrator + CLI build jobs from recipes and coordinate servers, clients, monitors.
- Services: Ollama or vLLM (single or Ray-based distributed); clients send workload and export metrics.
- Monitor: node + workload metrics -> Pushgateway -> Prometheus -> Grafana.
- Diagrams: [diagrams/system-overview.mmd](diagrams/system-overview.mmd), [diagrams/data-flow.mmd](diagrams/data-flow.mmd).

## 3. Installation & Setup
- Requirements: Python 3.8+, Slurm access, Apptainer/Singularity; optional Docker for local monitoring.
- Quick install:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install flask requests psutil prometheus_client pyyaml
```
- On MeluXina: configure SSH, load Apptainer, pull containers:
```bash
module load Apptainer
apptainer pull docker://ollama/ollama:latest
apptainer pull docker://vllm/vllm-openai:latest
apptainer pull docker://python:3.12.3-slim
```

## 4. Quick Start Guide

### 4.1 Run Your First Benchmark

```bash
# Set Python path
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Run with default recipe
python3 src/benchmark/orchestrator.py \
  --server-nodes node001 \
  --client-nodes node002 node003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml
```

### 4.2 Monitoring Metrics with CLI

**Step 0: Put your correct meluxina user**
```bash
USER=u103217 
# or any of yours
```

**Step 1: Start local monitoring stack**
```bash
cd monitoring && ./start.sh
```

**Step 2: Deploy and run benchmark**
```bash
cd ../src
python3 benchmark_cli.py run --recipe src/recipes/ollama_meluxina.yaml
# Input cluster alias: meluxina
# Input remote path: /mnt/tier2/users/u103217/ollama-test  # Use YOUR username
# Note the Job ID from output
```

**Step 3: Setup monitoring tunnels automatically**
```bash
# Check job status first
ssh meluxina "squeue -u $USER"

# Setup tunnels (replace JOBID with your job number)
cd ..
./setup_monitoring.sh JOBID ollama    # For Ollama
./setup_monitoring.sh JOBID vllm      # For vLLM
```

**Step 4: View metrics**
```bash
# Check metrics endpoint
curl http://localhost:25000/metrics/prometheus | head -20  # Ollama
curl http://localhost:25002/metrics/prometheus | head -20  # vLLM

# Open Grafana
open http://localhost:3001
# Login: admin / admin
# Dashboards: "Ollama — Workload Overview" or "vLLM — Workload Overview"
```

**Manual tunnel setup (if needed):**
```bash
# Find client nodes
ssh meluxina "scontrol show job JOBID | grep StdOut | awk -F'=' '{print $2}' | xargs cat | grep 'Client nodes'"

# Create tunnels (replace mel2XXX with actual node names)
ssh -N -L 25000:mel2XXX:6000 meluxina &  # Ollama
ssh -N -L 25002:mel2XXX:6000 meluxina &  # vLLM
```

### 4.3 Quick Benchmark with Monitoring

```bash
# Terminal 1: Start local monitoring stack
cd monitoring && ./start.sh

# Terminal 2: Run benchmark with monitoring enabled
python3 src/benchmark/orchestrator.py \
  --server-nodes mel2001 \
  --client-nodes mel2002 mel2003 \
  --workload-config-file src/src/recipes/ollama_meluxina.yaml \
  --enable-monitoring \
  --pushgateway-node mel2109 \
  --monitor-interval 2

# Terminal 3: Open SSH tunnel for metrics
ssh -fN -L 25000:mel2002:6000 meluxina

# View metrics in Grafana
open http://localhost:3001
```

## 5. CLI Reference
- List recipes: `python3 src/benchmark_cli.py list`
- Run recipe: `python3 src/benchmark_cli.py run --recipe <path>`
- Create recipe interactively: `python3 src/benchmark_cli.py create`
- Full flag list: [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md#cli)
- See logs: `python3 src/benchmark_cli.py logs`

## 6. Recipe Configuration (key settings)
- Schema: [schemas/recipe-format.yaml](schemas/recipe-format.yaml); examples: [src/src/recipes](src/src/recipes).
- Minimal skeleton:
```yaml
scenario: "demo"
partition: "gpu"
workload:
  service: "ollama"   # or vllm
  duration: "2m"
  model: "llama2"
resources:
  servers: {gpus: 1}
  clients: {gpus: 0, clients_per_node: 4}
```
- Monitoring fields: `--enable-monitoring`, `--pushgateway-node`, `monitor_interval` (CLI) or set `monitor` section in recipes.
- Distributed vLLM: set `servers.service_config.distributed.enabled: true`, tune `tensor_parallel_size` / `pipeline_parallel_size`; see [src/src/recipes/vllm_meluxina_distributed.yaml](src/src/recipes/vllm_meluxina_distributed.yaml).
- Validation: required `scenario`, `partition`, `resources`, `workload`, `orchestration`; container paths must end with `.sif`; `prompt_len` required for synthetic vLLM workloads.

## 7. Monitoring & Metrics
- Start local stack: `cd monitoring && ./start.sh` (Prometheus :9092, Grafana :3001).
- Tunnel to client metrics: `ssh -fN -L 25000:melXXXX:6000 meluxina`; check `http://localhost:25000/metrics/prometheus`.
- Dashboards: `monitoring/grafana/dashboards` (Ollama, vLLM).

## 8. Distributed Benchmarking
- Enable Ray in recipe (`distributed.enabled: true`) and set tensor/pipeline parallel sizes.
- Use the distributed template: [src/src/recipes/vllm_meluxina_distributed.yaml](src/src/recipes/vllm_meluxina_distributed.yaml).

## 9. Extending the Framework
- Implement `ServerManager`, `WorkloadController`, and `WorkloadExecutor`, then register in `ServiceFactory`.
- Reuse monitoring/logging hooks; extend `Monitor` for custom metrics.

## 10. API Reference
- See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) and [schemas/recipe-format.yaml](schemas/recipe-format.yaml) for full interfaces.

## 11. Troubleshooting
- Server health: `curl http://<server>:11434/api/tags` (Ollama), `curl http://<server>:8000/health` (vLLM).
- Executor health: `curl http://<client>:6000/health`.
- Metrics missing: ensure tunnel + monitoring stack, then `curl http://localhost:25000/metrics/prometheus`.
- Slurm status: `squeue -u $USER`, `sinfo -p gpu`.

## 12. Best Practices
- Start with small/short runs and include warmup.
- Pin container digests; record seed and git commit in recipes.
- Keep monitor interval modest (1–5s) and save CSV metrics for later analysis.

## License
Licensed under the terms in LICENSE.

## Support
Use the issue tracker for bugs and feature requests.
