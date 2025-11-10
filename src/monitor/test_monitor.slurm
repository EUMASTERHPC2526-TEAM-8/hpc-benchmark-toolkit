#!/bin/bash
#SBATCH --job-name=test_monitor
#SBATCH --account=p200776
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1              # Request one GPU
#SBATCH --time=00:10:00
#SBATCH --output=test_monitor.out
#SBATCH --error=test_monitor.err
#SBATCH --partition=gpu           # GPU partition
#SBATCH --qos=default
#SBATCH --mem=32G

# ----------------------------
# Environment setup
# ----------------------------
module load Python
module load CUDA/12.2.0           # adjust if your system uses a different CUDA version

# ----------------------------
# Paths for metric output
# ----------------------------
# Save metrics in the same directory where the script is executed
export MONITOR_OUTPUT_DIR="$PWD/monitor_output"
mkdir -p "$MONITOR_OUTPUT_DIR"

echo "Working directory: $PWD"
echo "Metrics will be saved in: $MONITOR_OUTPUT_DIR"

# ----------------------------
# Run the monitor
# ----------------------------
python test_monitor.py \
    --log_console=True \
    --export_json=True \
    --export_csv=True \
    --interval=5 \
    --output_dir="$MONITOR_OUTPUT_DIR" \
    --max_duration=120

echo "Monitor finished. Results saved in: $MONITOR_OUTPUT_DIR"

