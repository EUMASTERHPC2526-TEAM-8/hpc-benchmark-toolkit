#!/bin/bash

# Quick start script for local monitoring stack

set -e

echo "=========================================="
echo "HPC Monitoring Stack - Quick Start"
echo "=========================================="

cd "$(dirname "$0")"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null && ! docker-compose --version &> /dev/null; then
    echo "Error: Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Check if already running
if docker ps | grep -q "hpc-prometheus\|hpc-grafana"; then
    echo "Monitoring stack is already running!"
    echo ""
    read -p "Do you want to restart it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing containers..."
        docker compose down
    else
        echo "Exiting..."
        exit 0
    fi
fi

# Start stack
echo ""
echo "[1] Starting monitoring stack..."
docker compose up -d

# Ports aligned with docker-compose.yml mappings
PROM_PORT=9092
GRAFANA_PORT=3001
PUSHGATEWAY_PORT=9093

# Wait for services
echo ""
echo "[2] Waiting for services to be ready..."

wait_http() {
    url="$1"; name="$2"; timeout=40; interval=2
    echo -n "  Checking ${name}... "
    for _ in $(seq 1 $((timeout/interval))); do
        if curl -fsS "$url" > /dev/null; then
            echo "✓"
            return 0
        fi
        sleep $interval
    done
    echo "✗"
    echo "Warning: ${name} may not be ready yet (${url})"
    return 1
}

# Check Prometheus
wait_http "http://localhost:${PROM_PORT}/-/healthy" Prometheus

# Check Grafana
wait_http "http://localhost:${GRAFANA_PORT}/api/health" Grafana

# Check Pushgateway
wait_http "http://localhost:${PUSHGATEWAY_PORT}/metrics" Pushgateway

echo ""
echo "=========================================="
echo "✓ Monitoring Stack Started!"
echo "=========================================="
echo ""
echo "Services:"
echo "  📊 Prometheus:   http://localhost:${PROM_PORT}"
echo "  📈 Grafana:      http://localhost:${GRAFANA_PORT} (admin/admin)"
echo "  🔀 Pushgateway:  http://localhost:${PUSHGATEWAY_PORT}"
echo ""
echo "To test locally:"
echo "  cd ../src/monitor"
echo "  python3 run_local_monitor.py"
echo ""
echo "To view logs:"
echo "  docker compose logs -f"
echo ""
echo "To stop:"
echo "  docker compose down"
echo ""
echo "To connect to MeluXina Pushgateway:"
echo "  1. Start SSH tunnel: ssh -L 19091:NODE:9091 user@login.meluxina.lu"
echo "  2. Add target host.docker.internal:19091 in prometheus.yml (if not present)"
echo "  3. Restart Prometheus: docker compose restart prometheus"
echo ""
