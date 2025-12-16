# Quickstart: Ollama Benchmark with Live Metrics in Grafana

Run Ollama LLM benchmarks on MeluXina HPC and monitor live metrics in Grafana.

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
export WORKSPACE="$../hpc-benchmark-toolkit"
#My case
export WORKSPACE="/Users/giovanni/Documents/Università/CorsiDaSuperare/SoftwareAtelierChallenge/hpc-benchmark-toolkit"
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

sed -i '' "s/account: .*/account: \"$MLUX_ACCOUNT\"/" \
  $WORKSPACE/src/src/recipes/vllm_meluxina_distributed.yaml

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

## Step 5 — Deploy and run benchmark (Ollama or VLLM)

```bash
cd $WORKSPACE/src

# Create output directory with timestamp
OUTPUT_DIR=/home/users/$MLUX_USER/benchmark_$(date +%Y%m%d_%H%M%S)

# Deploy and submit Ollama
./deploy_and_run.sh \
  src/recipes/ollama_meluxina.yaml \
  meluxina \
  $OUTPUT_DIR

# Deploy and submit vLLM
./deploy_and_run.sh \
  src/recipes/vllm_meluxina_distributed.yaml \
  meluxina \
  $OUTPUT_DIR

# Wait for job to start (check until STATE is RUNNING)
ssh meluxina "squeue -u \$USER"
```

---

## Step 6 — Find executor nodes and open SSH tunnels

Once job is RUNNING, find which nodes have the workload executor (port 6000):

```bash
# Get your job ID
ssh meluxina "squeue -u \$USER -o '%i %N'"
# Example output: 3855777 mel[2163-2164,2181-2183]

JOBID="3855777"  # Replace with your actual job ID
```

### Quick Method: Find nodes with port 6000

```bash
# Test all nodes to find which have port 6000 (workload executor with metrics)
# Example:
for node in mel2163 mel2164 mel2181 mel2182 mel2183; do 
  echo -n "$node: " 
  ssh meluxina "srun --jobid=$JOBID -N1 -w $node --overlap ss -tulpn 2>/dev/null | grep ':6000' && echo 'EXECUTOR FOUND' || echo 'no'" 
done

# Example output:
# mel2163: no
# mel2164: no
# melABCD: tcp LISTEN 0 128 0.0.0.0:6000 0.0.0.0:* users:(("python3",pid=26558,fd=3)) EXECUTOR FOUND
# melABCD: tcp LISTEN 0 128 0.0.0.0:6000 0.0.0.0:* users:(("python3",pid=28113,fd=3)) EXECUTOR FOUND
# mel2183: no
```

From the output above, you found **melABCD** and **melEFGH** have port 6000. Now open tunnels:

```bash
# Terminal 1
ssh -N -L 25000:melABCD:6000 meluxina

# Terminal 2 (open new terminal)
ssh -N -L 25001:melEFGH:6000 meluxina
```

Or run both in background:

```bash
ssh -N -L 25000:mel2181:6000 meluxina &
ssh -N -L 25001:mel2182:6000 meluxina &

# Verify tunnels work
curl -s http://localhost:25000/health
curl -s http://localhost:25001/health
# Expected: {"service":"ollama","status":"ok"} or {"service":"vllm","status":"ok"}
```

### Alternative: Use the automated script

```bash
# Copy script to MeluXina and run
scp monitoring/find_executor_nodes.sh meluxina:~
ssh meluxina ./find_executor_nodes.sh $JOBID

# Copy the SSH tunnel commands from output and run them
```

**⚠️ NOTE:** Port 6000 is the workload executor where Prometheus metrics are exposed at `/metrics/prometheus`.

---

## Step 7 — Verify tunnels and check metrics

Test that tunnels are working:

```bash
# Check health endpoints
curl -s http://localhost:25000/health
curl -s http://localhost:25001/health
# Expected: {"service":"ollama","status":"ok"} or {"service":"vllm","status":"ok"}

# Check Prometheus metrics are available
curl -s http://localhost:25000/metrics/prometheus | head -20
curl -s http://localhost:25001/metrics/prometheus | head -20
# Should see ollama_* or vllm_* metrics
```

---

## Step 8 — View live metrics in Grafana

1. Open **http://localhost:3001** (username: admin, password: admin)

2. Click **Dashboards** (left sidebar)

3. Select a pre-made dashboard:
   - **"vLLM — Workload Overview"** — for vLLM metrics
   - **"Ollama — Workload Overview"** — for Ollama metrics

4. Or manually explore via **Explore** (🧭 icon):
   - Click **Prometheus** as data source
   - Try a query like: `vllm_requests_total{job="vllm-clients"}` or `ollama_requests_total{job="ollama-clients"}`
   - Click **Run query**

5. **Enable auto-refresh**: Top-right dropdown → select **5s**

**Example queries:**

```promql
# vLLM throughput
sum(rate(vllm_requests_total[1m])) by (job)

# Ollama request count
sum(ollama_requests_total) by (instance)

# Workload status (1 = running, 0 = done)
vllm_workload_running

# Request latency (vLLM)
histogram_quantile(0.95, vllm_request_latency_seconds)
```

---

## Step 9 — Check results after completion

4. Puoi usare uno dei dashboard pronti (già provisionati):
  - “vLLM — Workload Overview” (solo metriche `vllm_*`)
  - “Ollama — Workload Overview” (solo metriche `ollama_*`)
  - “LLM Workloads: vLLM & Ollama” (vista combinata)
  - Nota: i pannelli con `rate(...)` mostrano 0 se non c’è traffico recente. Per carichi intermittenti usa `increase(...[5m])`.

Oppure prova manualmente queste query in Explore:

### vLLM
```promql
vllm_workload_running
```
```promql
sum by (host) (vllm_requests_total)
```
```promql
sum by (host) (rate(vllm_requests_total[1m]))
```
```promql
sum(vllm_throughput_rps) by (host)
```
```promql
avg(vllm_request_latency_seconds)
```

### Ollama (se abilitato nella ricetta)
```promql
ollama_workload_running
```
```promql
sum by (instance) (ollama_requests_total)
```
```promql
sum by (instance) (rate(ollama_requests_total[1m]))
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
pkill -f "ssh.*25000:.*:6000" || true
pkill -f "ssh.*25001:.*:6000" || true

# Get your job ID and node list
ssh meluxina "squeue -u \$USER -o '%i %N' -h"

# Find which node has port 6000 (as shown in Step 6)
# Then open new tunnel(s) with the correct executor node(s)
ssh -N -L 25000:mel<EXECUTOR_NODE>:6000 meluxina

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
# 1) I tunnel devono essere attivi sulle porte 25000/25001 dell'host
lsof -nP -iTCP:25000-25001 -sTCP:LISTEN

# 2) Ricrea i tunnel se necessario
pkill -f 'ssh.*25000:.*:6000' || true
pkill -f 'ssh.*25001:.*:6000' || true
ssh -fN -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -L 25000:mel2102:6000 meluxina
ssh -fN -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -L 25001:mel2147:6000 meluxina

# 3) Verifica dal container che host.docker.internal sia raggiungibile
docker exec hpc-prometheus sh -lc 'wget -qO- http://host.docker.internal:25000/health || true'

# 4) Reload Prometheus (se hai modificato prometheus.yml)
curl -X POST http://localhost:9092/-/reload
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MeluXina HPC                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  mel2033    │  │  mel2034    │  │  mel2035    │         │
│  │   vLLM/Oll. │  │  Executor 1 │  │ Executor 2 │         │
│  │  (serving)  │◄─│   :6000     │  │   :6000     │         │
│  └─────────────┘  └──────┬──────┘  └─────────────┘         │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │ SSH Tunnel
                           │ -L 25000:mel2102:6000
                           │ -L 25001:mel2147:6000
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                         Laptop                              │
│  ┌─────────────┐       ┌─────────────┐                     │
│  │  Prometheus │──────►│   Grafana   │                     │
│  │   :9092     │scrape │   :3001     │                     │
│  └──────┬──────┘       └─────────────┘                     │
│         │                                                   │
│         ▼ scrapes host.docker.internal:25000/metrics/prom.  │
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

# 5. Open tunnels
ssh -fN -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -L 25000:mel2102:6000 meluxina
ssh -fN -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -L 25001:mel2147:6000 meluxina

# 6. Open Grafana
open http://localhost:3001
# Login: admin/admin
# Apri il dashboard: "LLM Workloads: vLLM & Ollama"
# In Explore prova: vllm_requests_total, sum by (host) (rate(vllm_requests_total[1m]))