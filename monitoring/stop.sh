#!/bin/bash

# Stop monitoring stack

cd "$(dirname "$0")"

echo "Stopping monitoring stack..."
docker compose down

echo ""
echo "✓ Monitoring stack stopped"
echo ""
echo "To remove volumes (data will be lost):"
echo "  docker compose down -v"
echo ""
