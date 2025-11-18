# Quickstart: from zero to Grafana in ~15 minutes

This is how I set up the full monitoring pipeline end to end: MeluXina node → Pushgateway → SSH tunnel → Prometheus → Grafana.

## Prerequisites

- Docker on my laptop
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
# Replace <node> with the value from squeue NODELIST (e.g., melxxxx)
ssh -p 8822 -i ~/.ssh/id_ed25519_mlux -N -L 19091:<node>:9091 u103217@login.lxp.lu
```

Keep this terminal open. Prometheus will scrape the tunneled target at http://localhost:19091.

---

## Part 5 — Quick local sanity check (optional, 2 min)

I like to verify the local pipeline before using MeluXina metrics: ## No need to do it anymore

```bash
cd src/monitor
python3 run_local_monitor.py
```

This pushes to the local Pushgateway on port 9093 (from docker-compose). I should see data in Grafana.

---

## Part 6 — Run the Monitor on a MeluXina compute node (3–5 min)

Allocate a node and set up a small venv:

```bash
salloc -A <account> -p <partition> -N 1 --t 15
## for me: salloc -q default -p gpu --time=15 -A p200981

#Vrtual environment setting
python3 -m venv .venv
source .venv/bin/activate
pip install psutil prometheus_client requests
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

## Using the Monitor from the orchestrator

At minimum, I pass the Pushgateway URL to the Monitor configuration.

Option A — Hardcode (quick and dirty):

```python
monitor_config = {
    "output_file": args.monitor_output,
    # ... other options ...
    "prometheus_pushgateway_url": "http://mel0042:9091",  # replace with your node
}
```

Option B — CLI argument (flexible):

```python
parser.add_argument("--pushgateway-url", type=str, help="Prometheus Pushgateway URL")
if args.pushgateway_url:
    monitor_config["prometheus_pushgateway_url"] = args.pushgateway_url
```

Then run:

```bash
python src/benchmark/orchestrator.py \
  --enable-monitoring \
  --monitor-interval 2 \
  --monitor-output results/metrics.csv \
  --pushgateway-url "http://mel0042:9091"
```

---

## Pro tips

- Keep the Pushgateway job alive:
  ```bash
  squeue -u "$USER" -n pushgateway
  # Restart if needed
  cd monitoring/meluxina && mkdir -p logs && sbatch start_pushgateway.sh
  ```

- SSH tunnel convenience (~/.ssh/config):
  ```
  Host meluxina-tunnel
      HostName meluxina.lxp.lu
      User u103217
      LocalForward 19091 mel0042:9091
  ```
  Then: `ssh -p 8822 -i ~/.ssh/id_ed25519_mlux meluxina-tunnel`

---

## Troubleshooting

No data in Grafana:
```bash
# 1) Check the tunneled Pushgateway
curl -s http://localhost:19091/metrics | head -20

# 2) Check Prometheus targets
curl -s http://localhost:9092/api/v1/targets | jq '.data.activeTargets[] | {labels: .labels, health: .health, lastError: .lastError}'

# 3) Restart the local stack
cd monitoring && ./stop.sh && ./start.sh
```

SSH tunnel keeps dropping:
```bash
brew install autossh   # macOS
autossh -M 0 -N -L 19091:mel0042:9091 -p 8822 -i ~/.ssh/id_ed25519_mlux u103217@login.lxp.lu
```

Monitor can’t push:
```bash
echo "$PUSHGATEWAY_URL"   # verify the URL you are using

cat <<EOF | curl --data-binary @- http://mel0042:9091/metrics/job/test
# TYPE test_metric gauge
test_metric 42
EOF

curl -s http://mel0042:9091/metrics | grep test_metric
```

---

## What I expect to work at the end

- Monitor collects CPU/RAM/GPU metrics on MeluXina
- Pushgateway (on the node) stores the latest metrics
- Prometheus (local) scrapes via the SSH tunnel
- Grafana (local) shows everything in near real-time

Total time: about 15 minutes.
