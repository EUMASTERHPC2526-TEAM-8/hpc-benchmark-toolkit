#!/bin/bash
# Setup monitoring tunnels for HPC benchmark jobs
# Usage: ./setup_monitoring.sh JOBID [service_type]
# Example: ./setup_monitoring.sh 3942375 vllm

set -e

JOBID=${1:-}
SERVICE_TYPE=${2:-ollama}

if [ -z "$JOBID" ]; then
    echo "Usage: $0 JOBID [service_type]"
    echo "  JOBID: Slurm job ID (get from squeue)"
    echo "  service_type: ollama or vllm (default: ollama)"
    echo ""
    echo "Example: $0 3942375 vllm"
    exit 1
fi

CLUSTER="meluxina"

echo "==> Checking job status..."
ssh $CLUSTER "squeue -j $JOBID" || {
    echo "ERROR: Job $JOBID not found or not running"
    exit 1
}

echo ""
echo "==> Finding client nodes from job logs..."
CLIENT_NODES=$(ssh $CLUSTER "scontrol show job $JOBID | grep StdOut | awk -F'=' '{print \$2}' | xargs cat 2>/dev/null | grep -oP 'Client nodes: \K.*' || echo ''")

if [ -z "$CLIENT_NODES" ]; then
    echo "WARNING: Could not find client nodes in logs yet."
    echo "Job might still be starting. Wait a moment and try again."
    echo ""
    echo "To check logs manually:"
    LOG_FILE=$(ssh $CLUSTER "scontrol show job $JOBID | grep StdOut | awk -F'=' '{print \$2}'")
    echo "  ssh $CLUSTER \"tail -f '$LOG_FILE'\""
    exit 1
fi

echo "Client nodes found: $CLIENT_NODES"
NODE_ARRAY=($CLIENT_NODES)

# Kill existing tunnels on these ports
echo ""
echo "==> Cleaning up old tunnels..."
if [ "$SERVICE_TYPE" = "ollama" ]; then
    PORTS=(25000 25001)
else
    PORTS=(25002 25003)
fi

for port in "${PORTS[@]}"; do
    pkill -f "ssh.*-L ${port}:" 2>/dev/null || true
done

# Create new tunnels
echo ""
echo "==> Creating SSH tunnels..."
for i in "${!NODE_ARRAY[@]}"; do
    node=${NODE_ARRAY[$i]}
    port=${PORTS[$i]}
    
    echo "  Tunnel: localhost:$port -> $node:6000"
    ssh -f -N -L ${port}:${node}:6000 $CLUSTER
    sleep 1
done

echo ""
echo "==> Verifying connections..."
success=0
for port in "${PORTS[@]}"; do
    if curl -s http://localhost:${port}/health >/dev/null 2>&1; then
        echo "  ✓ Port $port: OK"
        success=$((success + 1))
    else
        echo "  ✗ Port $port: Connection failed"
        echo "    (Client may still be starting up)"
    fi
done

echo ""
echo "==> Setup complete!"
echo ""
echo "Monitor with:"
echo "  curl http://localhost:${PORTS[0]}/metrics/prometheus | head -20"
echo ""
echo "Open Grafana:"
echo "  open http://localhost:3001"
echo "  Dashboard: $SERVICE_TYPE — Workload Overview"
echo ""
echo "To stop tunnels:"
for port in "${PORTS[@]}"; do
    echo "  pkill -f 'ssh.*-L ${port}:'"
done
echo ""

if [ $success -eq 0 ]; then
    echo "WARNING: No client responded. Check job logs:"
    LOG_FILE=$(ssh $CLUSTER "scontrol show job $JOBID | grep StdOut | awk -F'=' '{print \$2}'")
    echo "  ssh $CLUSTER \"tail -50 '$LOG_FILE'\""
fi
