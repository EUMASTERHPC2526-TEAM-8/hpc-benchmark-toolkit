# 🎯 SETUP RAPIDO: Da Zero a Grafana in 15 Minuti

Questa guida ti porta dall'installazione iniziale alla visualizzazione delle metriche in Grafana nel modo più rapido possibile.

## ✅ Prerequisiti

- Docker installato localmente
- Accesso SSH a MeluXina
- Python 3.x con psutil e prometheus_client installati

## 🚀 Parte 1: Setup MeluXina (5 minuti)
Copy all the data inside meluxina (without github)
```bash
# Dal tuo Mac, dalla directory del repo:
cd ~/Documents/Università/CorsiDaSuperare/SoftwareAtelierChallenge

rsync -av --progress -e "ssh -p 8822 -i ~/.ssh/id_ed25519_mlux" \
--exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='test_metrics.csv' \
hpc-benchmark-toolkit \
u103217@login.lxp.lu:/home/users/u103217/
```

### 1. Accedi a MeluXina
```bash
ssh -p 8822 -i ~/.ssh/id_ed25519_mlux u103217@login.lxp.lu
cd ~/hpc-benchmark-toolkit
```

### 2. Setup Pushgateway
```bash
cd monitoring/meluxina

# Rendi eseguibili gli script
chmod +x *.sh

#lancia un job con salloc e poi apptainer module load
salloc -q default -p gpu --time=15 -A p200981

# Esegui setup automatico
./setup_meluxina.sh

# Output ti darà il JOB_ID, salvalo!
```

### 3. Ottieni URL Pushgateway
```bash
# Aspetta qualche secondo che il job parta
sleep 10

# Trova il nodo
./test_pushgateway.sh

# Output sarà tipo: "http://mel0042:9091"
# SALVA QUESTO URL!
```

## 🖥️ Parte 2: Setup Locale (3 minuti)

### 1. Avvia Stack Docker
```bash
# Sul tuo computer locale
cd monitoring
chmod +x start.sh stop.sh
./start.sh

# Aspetta che tutto sia pronto
```

### 2. Apri SSH Tunnel (porta locale 19091)
```bash
# In un altro terminale (sostituisci mel0042 con il tuo nodo reale)
# Variante semplice (login risolve il compute node):
ssh -p 8822 -i ~/.ssh/id_ed25519_mlux -N -L 19091:$NODE$:9091 u103217@login.lxp.lu

# LASCIA QUESTO TERMINALE APERTO!
```

## 🧪 Parte 3: Test Locale (2 minuti)

```bash
# Sul tuo computer
cd src/monitor

# Avvia monitor di test
python3 run_local_monitor.py

# Dovresti vedere metriche ogni secondo
# Il monitor pusha automaticamente a http://localhost:9093 (Pushgateway del docker-compose)
```

## 📊 Parte 4: Visualizza in Grafana (2 minuti)

1. Apri browser: **http://localhost:3001**
2. Login: **admin** / **admin**
3. Vai su Dashboards → "HPC Benchmark Monitor"
4. Dovresti vedere grafici con metriche del tuo computer!

Se vedi i grafici → **SUCCESSO! 🎉**

## 🏔️ Parte 5: Test su MeluXina (3 minuti)

### 1. Esegui il monitor sul nodo (senza Apptainer)
Alloca un nodo ed esegui Python con un venv minimale.

```bash
salloc -A <account> -p <partition> -N 1 -t 00:10:00

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install psutil prometheus_client requests

# Avvia il Pushgateway sul nodo (se non già attivo)
# Assicurati che ci sia un pushgateway in ascolto su :9091
```bash
# Su MeluXina dopo salloc -N1 (esempio: nodo mel2133)

# PRIMA: Avvia Pushgateway in background su questo nodo
cd ~/hpc-benchmark-toolkit/monitoring/meluxina
./setup_meluxina.sh &
sleep 10  # Aspetta che sia pronto

# VERIFICA che Pushgateway funzioni
curl -s http://localhost:9091/metrics | head -5
# Dovresti vedere metriche prometheus

# POI: Esegui il monitor per 60s verso localhost:9091
cd ~/hpc-benchmark-toolkit/src/monitor
python3 - <<'PY'
import sys, os
sys.path.insert(0, os.path.expanduser('~/hpc-benchmark-toolkit/src'))
from monitor.monitor import Monitor

m = Monitor(
    output_file='test_metrics.csv',
    interval=2,
    log_console=True,
    metrics=('gpu','cpu','ram'),
    max_duration=60,
    prometheus_pushgateway_url='http://localhost:9091',
    prometheus_grouping_labels={'test':'meluxina'},
)
m.run()
PY
```

### 3. Verifica in Grafana
- Torna su http://localhost:3001
- Refresh dashboard
- Dovresti vedere metriche da un nodo MeluXina!
- Guarda il campo `instance` per vedere l'hostname del nodo

Se vedi metriche da MeluXina → **PIENO SUCCESSO! 🚀**

## 🎉 Congratulazioni!

Hai completato il setup! Ora puoi:

### Usare monitoring nei benchmark
```bash
python src/benchmark/orchestrator.py \
    --server-nodes node1 node2 \
    --client-nodes node3 \
    --workload-config-file config.json \
    --enable-monitoring \
    --monitor-interval 2 \
    --monitor-output results/metrics.csv
```

Ma prima devi configurare il Pushgateway URL nell'orchestrator...

### Opzione 1: Hardcode URL (veloce)
Modifica `src/benchmark/orchestrator.py`:

```python
# Trova questa riga
monitor_config = {
    "output_file": args.monitor_output,
    # ... altre opzioni ...
}

# Aggiungi
monitor_config["prometheus_pushgateway_url"] = "http://mel0042:9091"  # Sostituisci
```

### Opzione 2: Auto-detect (elegante)
```python
# All'inizio di orchestrator.py
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'monitoring', 'meluxina'))
from detect_pushgateway import get_pushgateway_url

# Quando crei il monitor
pushgateway_url = get_pushgateway_url()
if pushgateway_url:
    monitor_config["prometheus_pushgateway_url"] = pushgateway_url
```

### Opzione 3: Argomento CLI (flessibile)
```python
# Aggiungi argomento
parser.add_argument("--pushgateway-url", type=str,
                   help="Prometheus Pushgateway URL")

# Usa nell'orchestrator
if args.pushgateway_url:
    monitor_config["prometheus_pushgateway_url"] = args.pushgateway_url
```

Poi esegui:
```bash
python orchestrator.py \
    --pushgateway-url "http://mel0042:9091" \
    --enable-monitoring \
    # ... altri args
```

## 🔥 Pro Tips

### Mantenere Pushgateway sempre attivo
```bash
# Su MeluXina - controlla ogni giorno
squeue -u $USER -n pushgateway

# Se non è running, riavvia
sbatch monitoring/meluxina/start_pushgateway.sh
```

### SSH Tunnel automatico
Crea `~/.ssh/config`:
```
Host meluxina-tunnel
    HostName meluxina.lxp.lu
    User your_username
    LocalForward 9091 mel0042:9091
```

Poi:
```bash
ssh meluxina-tunnel
```

### Grafana Alerts
1. In Grafana → Alerting → Alert rules
2. Create alert rule
3. Query: `cpu_usage_percent > 90`
4. Notification channel: email/slack

### Dashboard personalizzato
1. Duplicate dashboard
2. Add panel → Add Query
3. Query: `rate(monitor_samples_total[5m])`
4. Save

## 🆘 Troubleshooting Rapido

### "No data in Grafana"
```bash
# 1. Verifica Pushgateway (tunnel locale)
curl http://localhost:19091/metrics | grep cpu_usage

# 2. Verifica Prometheus
curl http://localhost:9092/api/v1/targets

# 3. Restart tutto
docker compose restart
```

### "SSH tunnel disconnected"
```bash
# Usa autossh per riconnessione automatica
brew install autossh  # Mac
apt install autossh   # Linux

autossh -M 0 -L 19091:mel0042:9091 meluxina.lxp.lu
```

### "Monitor not pushing"
```bash
# Verifica URL
echo $PUSHGATEWAY_URL

# Test manuale
cat <<EOF | curl --data-binary @- http://mel0042:9091/metrics/job/test
# TYPE test_metric gauge
test_metric 42
EOF

# Verifica
curl http://mel0042:9091/metrics | grep test_metric
```

## 📚 Next Steps

- [ ] Configurare alert rules
- [ ] Creare dashboard personalizzati
- [ ] Esportare metriche in CSV da Grafana
- [ ] Integrare con CI/CD pipeline
- [ ] Setup long-term storage (Thanos)

## ✨ Fatto!

Hai un sistema di monitoring completo:
- ✅ Monitor raccoglie metriche HPC
- ✅ Pushgateway conserva metriche da job SLURM
- ✅ Prometheus aggrega tutto
- ✅ Grafana visualizza real-time

**Tempo totale: ~15 minuti** ⚡
