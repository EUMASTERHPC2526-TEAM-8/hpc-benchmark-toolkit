# Quickstart: Ollama Benchmark with Live Metrics in Grafana

Run Ollama LLM benchmarks on MeluXina HPC and monitor live metrics in Grafana.

**Total time: ~15 minutes**

---

## Configuration

**Set your credentials once** (edit these values):

```bash
# Your MeluXina username
export MLUX_USER="YOUR_USERNAME"    # e.g., u103217

# Your project account
export MLUX_ACCOUNT="YOUR_ACCOUNT"  # e.g., p200981

# Path to your SSH key
export MLUX_KEY="~/.ssh/id_ed25519_mlux"

# Local workspace path
export WORKSPACE="$HOME/hpc-benchmark-toolkit"
```

---

## Prerequisites

- Docker Desktop running on your laptop
- SSH access to MeluXina with your key
- Account with GPU partition access

---

## Step 1 — Configure SSH alias

**On laptop:**

```bash
cat >> ~/.ssh/config << EOF

Host meluxina
    HostName login.lxp.lu
    Port 8822
    User $MLUX_USER
    IdentityFile $MLUX_KEY
EOF
```

**Test:**
```bash
ssh meluxina "echo Connected as \$USER"
```

---

## Step 2 — Clone and sync code

```bash
# Clone repo (if not already done)
git clone https://github.com/EUMASTERHPC2526-TEAM-8/hpc-benchmark-toolkit.git $WORKSPACE

# Sync to MeluXina
rsync -av --exclude='.git' --exclude='__pycache__' \
  $WORKSPACE meluxina:~/
```

---

## Step 3 — Update recipe with your account

```bash
# Edit recipe to use your account
sed -i '' "s/account: .*/account: \"$MLUX_ACCOUNT\"/" \
  $WORKSPACE/src/src/recipes/ollama_meluxina.yaml

# Verify
grep account $WORKSPACE/src/src/recipes/ollama_meluxina.yaml
```

---

## Step 4 — Start local monitoring stack

```bash
cd $WORKSPACE/monitoring
./start.sh

# Services available at:
# - Grafana:    http://localhost:3001 (admin/admin)
# - Prometheus: http://localhost:9092
```

---

## Step 5 — Deploy and run benchmark

```bash
cd $WORKSPACE/src

# Create output directory with timestamp
OUTPUT_DIR=/home/users/$MLUX_USER/benchmark_$(date +%Y%m%d_%H%M%S)

# Deploy and submit
./deploy_and_run.sh \
  src/recipes/ollama_meluxina.yaml \
  meluxina \
  $OUTPUT_DIR

# Wait for job to start (check until STATE is RUNNING)
ssh meluxina "squeue -u \$USER"
```

---

## Step 6 — Get allocated nodes

Once job is RUNNING:

```bash
# Get node list
ssh meluxina "squeue -u \$USER -o '%N' -h"

# Example output: mel[2033-2035]
# - First node (mel2033): Ollama server
# - Second node (mel2034): Client executor ← MONITOR THIS ONE
# - Third node (mel2035): Orchestrator
```

**Note the second node** (client) - you need it for the tunnel.

---

## Step 7 — Open SSH tunnel to client executor

**Replace `melXXXX` with your actual client node (second node from Step 6):**

```bash
# Open tunnel in background
ssh -fN -L 25000:melXXXX:6000 meluxina

# Example: ssh -fN -L 25000:mel2034:6000 meluxina

# Verify tunnel works
curl http://localhost:25000/health
# Should return: {"service":"ollama","status":"ok"}
```

---

## Step 8 — View live metrics in Grafana

1. Open **http://localhost:3001** (admin/admin)

2. Go to **Explore** (compass icon 🧭 in left sidebar)

3. Select **Prometheus** as data source

4. Try these queries:

### Workload Status
```promql
ollama_workload_running
```
Shows `1` when benchmark is running, `0` when complete.

### Requests & Throughput
```promql
ollama_requests_total
```
```promql
ollama_throughput_rps
```

### Latency
```promql
ollama_request_latency_seconds
```

### Errors
```promql
ollama_errors_total
```

5. Click **Run query** or press `Shift+Enter`

6. Enable **auto-refresh** (top right dropdown → 5s) to see live updates

---

## Step 10 — Check results after completion

```bash
ssh meluxina

# List your benchmark directories
ls -la ~/benchmark_*

# Navigate to latest output directory
cd ~/benchmark_*/experiments/*/

# View aggregated logs
cat stdout.log

# View orchestrator summary
tail -50 orchestrator.log
```

---

## Quick Reference

### Start new benchmark
```bash
cd $WORKSPACE/src
OUTPUT_DIR=/home/users/$MLUX_USER/benchmark_$(date +%Y%m%d_%H%M%S)
./deploy_and_run.sh src/recipes/ollama_meluxina.yaml meluxina $OUTPUT_DIR
```

### Update tunnel for new job
```bash
# Kill old tunnels
pkill -f "ssh.*25000"

# Get client node (second in list)
ssh meluxina "squeue -u \$USER -o '%N' -h"

# Open new tunnel (replace melXXXX)
ssh -fN -L 25000:melXXXX:6000 meluxina

# Verify
curl http://localhost:25000/health
```

### Check job status
```bash
ssh meluxina "squeue -u \$USER"
```

### Cancel job
```bash
ssh meluxina "scancel JOBID"
```

### Restart monitoring stack
```bash
cd $WORKSPACE/monitoring
./stop.sh && ./start.sh
```

---

## Metrics Reference

| Metric | Description | Type |
|--------|-------------|------|
| `ollama_workload_running` | 1 if benchmark running, 0 if complete | Gauge |
| `ollama_requests_total` | Total requests made | Counter |
| `ollama_errors_total` | Total errors | Counter |
| `ollama_request_latency_seconds` | Average latency in seconds | Gauge |
| `ollama_throughput_rps` | Requests per second | Gauge |
| `ollama_elapsed_seconds` | Total elapsed time | Gauge |
| `ollama_threads` | Number of concurrent threads | Gauge |

---

## Troubleshooting

### Job stuck in PENDING
```bash
# Check GPU availability
ssh meluxina "sinfo -p gpu"

# Check account permissions
ssh meluxina "sacctmgr show assoc user=\$USER format=account,partition"
```

### Tunnel connection refused
```bash
# Wait 60+ seconds after job starts for executor to initialize
# Check if port 6000 is open on node
ssh meluxina "squeue -u \$USER"  # Get job ID
ssh meluxina "srun --jobid=JOBID --nodelist=melXXXX ss -tulpn | grep 6000"
```

### No metrics in Grafana
```bash
# 1. Check Prometheus targets
open http://localhost:9092/targets
# ollama-clients should be UP

# 2. Verify tunnel is working
curl http://localhost:25000/health

# 3. Check metrics endpoint
curl http://localhost:25000/metrics/prometheus
```

### Permission denied on rsync
```bash
# OUTPUT_DIR must be absolute path
# ✅ Correct: /home/users/u103217/benchmark_20231203
# ❌ Wrong:   benchmark_20231203

echo $OUTPUT_DIR  # Verify it starts with /home/users/
```

### Prometheus target DOWN
```bash
# Kill and recreate tunnel
pkill -f "ssh.*25000"
ssh -fN -L 25000:melXXXX:6000 meluxina

# Restart Prometheus
cd $WORKSPACE/monitoring
docker compose restart prometheus
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MeluXina HPC                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  mel2033    │  │  mel2034    │  │  mel2035    │         │
│  │   Ollama    │  │   Client    │  │ Orchestrator│         │
│  │   Server    │◄─│  Executor   │◄─│             │         │
│  │   :11434    │  │   :6000     │  │             │         │
│  └─────────────┘  └──────┬──────┘  └─────────────┘         │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │ SSH Tunnel
                           │ -L 25000:mel2034:6000
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                         Laptop                              │
│  ┌─────────────┐       ┌─────────────┐                     │
│  │  Prometheus │──────►│   Grafana   │                     │
│  │   :9092     │scrape │   :3001     │                     │
│  └──────┬──────┘       └─────────────┘                     │
│         │                                                   │
│         ▼ scrapes localhost:25000/metrics/prometheus        │
│  ┌─────────────┐                                           │
│  │   Docker    │                                           │
│  │   Network   │                                           │
│  └─────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Example Session with Giovanni account

```bash
# 1. Set credentials
export MLUX_USER="u103217"
export MLUX_ACCOUNT="p200981"
export WORKSPACE="$HOME/hpc-benchmark-toolkit"

# 2. Start monitoring
cd $WORKSPACE/monitoring && ./start.sh

# 3. Deploy benchmark
cd $WORKSPACE/src
OUTPUT_DIR=/home/users/$MLUX_USER/benchmark_$(date +%Y%m%d_%H%M%S)
./deploy_and_run.sh src/recipes/ollama_meluxina.yaml meluxina $OUTPUT_DIR

# 4. Wait for RUNNING, get client node
ssh meluxina "squeue -u \$USER"
# Output: mel[2033-2035] → client is mel2034

# 5. Open tunnel
ssh -fN -L 25000:mel2034:6000 meluxina

# 6. Open Grafana
open http://localhost:3001
# Login: admin/admin
# Explore → Prometheus → ollama_requests_total → Run query
```