# Quickstart: from zero to Grafana in ~15 minutes

This is how I set up the full monitoring pipeline end to end: MeluXina node → Pushgateway → SSH tunnel → Prometheus → Grafana.

## Prerequisites

- Docker on my laptop needed to verify the correct execution
- SSH access to MeluXina (key + username)
- Python 3.x (I use a venv) with psutil and prometheus_client

---

## Part 1 — Copy the code to MeluXina (5 min)

On my laptop, from the repo directory to sync the source code with meluxina data:

```bash
cd ~/Documents/Università/CorsiDaSuperare/SoftwareAtelierChallenge

SSH to MeluXina and go to the repo:

```bash
ssh -p 8822 -i ~/.ssh/id_ed25519_mlux u103217@login.lxp.lu
cd ~/hpc-benchmark-toolkit
```

On another window then:

```bash
rsync -av --progress -e "ssh -p 8822 -i ~/.ssh/id_ed25519_mlux" \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='test_metrics.csv' \
  hpc-benchmark-toolkit \
  u103217@login.lxp.lu:/home/users/u103217/
```
##To be done just when data is changed, fter accessing and identifying the port
---

## Part 2 — Start Pushgateway on MeluXina (job on the cluster)

I run Pushgateway as a Slurm job so it survives my terminal sessions.

```bash
cd monitoring/meluxina
mkdir -p logs    # Slurm logs

# Submit the Pushgateway job (partition/account may need adjusting)
sbatch start_pushgateway.sh

# Check it's running and note the node name (NODES column)
squeue -u "$USER" -n pushgateway
```

Once the job is RUNNING, Pushgateway will listen on http://<compute-node>:9091 on that node.

---

## Part 3 — Start the local stack (Prometheus + Grafana + local Pushgateway)

On my laptop, no meluxina: 

```bash
cd monitoring
chmod +x start.sh stop.sh
./start.sh
```

Ports I use locally:
- Prometheus: http://localhost:9092
- Grafana: http://localhost:3001
- Local Pushgateway (for local tests only): http://localhost:9093

---

## Part 4 — Open the SSH tunnel from laptop → MeluXina

I forward a local port to the compute node where Pushgateway is running:

```bash
# Replace <node> with the value of the pushgateway from squeue NODELIST (e.g., melxxxx)
ssh -p 8822 -i ~/.ssh/id_ed25519_mlux -N -L 19091:<node>:9091 u103217@login.lxp.lu
```

Keep this terminal open. Prometheus will scrape the tunneled target at http://localhost:19091.

---

## Part 5 — Run the Monitor on a MeluXina compute node (3–5 min)

Allocate a node and set up a small venv:

```bash
salloc -A <account> -p <partition> -N 1 --t 15
## for me: salloc -q default -p gpu --time=30 -A p200981

# Virtual environment setup
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies (Monitor + Orchestrator)
pip install flask requests psutil prometheus_client pyyaml

```

Get the Pushgateway node hostname and verify it's reachable (do NOT assume localhost unless you allocated the same node):

```bash
PG_NODE=$(squeue -u u103217 -n pushgateway -h -o %N)
echo "Pushgateway node: $PG_NODE"
curl -s "http://$PG_NODE:9091/metrics" | head -5
export PUSHGATEWAY_URL="http://$PG_NODE:9091"
```

Run the Monitor for 60 seconds and push to that Pushgateway:

```bash
python3 - <<'PY'
import sys, os
sys.path.insert(0, os.path.expanduser('~/hpc-benchmark-toolkit/src'))
from monitor.monitor import Monitor

push_url = os.environ.get('PUSHGATEWAY_URL', 'http://localhost:9091')

m = Monitor(
    output_file='test_metrics.csv',
    interval=2,
    log_console=True,
    metrics=('gpu','cpu','ram'),
    max_duration=120,
    prometheus_pushgateway_url=push_url,
    prometheus_grouping_labels={'source':'meluxina'},
)
m_print = lambda msg: print(f"[monitor] {msg}")
m_print(f"Pushing to {push_url}")
m.run()
PY
```
---
## Part 7 — See the data in Grafana (2 min)

On my laptop:
1) Open http://localhost:3001 (Grafana)
2) Log in with admin / admin
3) Open the dashboard “HPC Benchmark Monitor”
4) I should see the time series from my laptop and from the MeluXina node (look at the instance label)

Success if data shows up. 🚀

---

## Part 8 — Using the Monitor from the orchestrator

The orchestrator has built-in monitoring support. Use it to collect metrics automatically during your benchmark runs.

### Find your allocated nodes

```bash
# Check your active jobs
squeue -u "$USER"

# If you have interactive allocations, get node names
scontrol show hostname $SLURM_JOB_NODELIST
```

### Run benchmark with monitoring

```bash
cd ~/hpc-benchmark-toolkit
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Find Pushgateway node
PG_NODE=$(squeue -u $USER -n pushgateway -h -o %N)
echo "Pushgateway node: $PG_NODE"

# Create dummy config for testing
cat > config.json << 'EOF'
{
  "service": "dummy",
  "model": "test-model",
  "clients_per_node": 1
}
EOF

# Get your allocated node
MYNODE=$(hostname)

# Run orchestrator with monitoring
python3 src/benchmark/orchestrator.py \
  --server-nodes $MYNODE \
  --client-nodes $MYNODE \
  --workload-config-file config.json \
  --enable-monitoring \
  --pushgateway-node $PG_NODE \
  --monitor-interval 2 \
  --monitor-output results/metrics.csv
```

**What happens:**
- Monitor runs in background thread during the entire benchmark
- Collects CPU/RAM/GPU metrics every 2 seconds
- Pushes to Pushgateway → visible in Grafana in real-time
- Saves local CSV to `results/metrics.csv`
- Dummy service completes immediately (for testing monitoring only)

**To see CPU oscillations in Grafana:**

Still to undestand how to create worklosd

**Check results:**

```bash
# View CSV
cat results/metrics.csv | tail -20

# Verify push to Pushgateway
curl -s http://$PG_NODE:9091/metrics | grep "cpu_usage_percent.*mel"
```

**Without monitoring** (original behavior):
```bash
python3 src/benchmark/orchestrator.py \
  --server-nodes mel2100 \
  --client-nodes mel2105 mel2004 \
  --workload-config-file config.json
```

---

## What I expect to work at the end

- Monitor collects CPU/RAM/GPU metrics on MeluXina
- Pushgateway (on the node) stores the latest metrics
- Prometheus (local) scrapes via the SSH tunnel
- Grafana (local) shows everything in near real-time

Total time: about 15 minutes.
