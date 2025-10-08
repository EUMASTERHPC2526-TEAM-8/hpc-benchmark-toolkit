#!/bin/bash
#
# This script handles the complete workflow:
# 1. Generate sbatch script from recipe
# 2. Copy benchmark folder and sbatch to cluster
# 3. Submit the job
#
# Usage:
#     ./deploy_and_run.sh <recipe.yaml> <cluster_host> <remote_path> [--no-interactive]
#     
# Examples:
#     ./deploy_and_run.sh recipes/ollama_meluxina.yaml meluxina.lxp.lu /project/home/p200776/team8
#     ./deploy_and_run.sh recipes/ollama_meluxina.yaml meluxina.lxp.lu /project/home/p200776/team8 --no-interactive

set -e  # Exit on error
set -u  # Exit on undefined variable

# Parse arguments
INTERACTIVE_MODE=true
RECIPE_FILE=""
CLUSTER_HOST=""
REMOTE_PATH=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-interactive)
            INTERACTIVE_MODE=false
            shift
            ;;
        *)
            if [ -z "$RECIPE_FILE" ]; then
                RECIPE_FILE="$1"
            elif [ -z "$CLUSTER_HOST" ]; then
                CLUSTER_HOST="$1"
            elif [ -z "$REMOTE_PATH" ]; then
                REMOTE_PATH="$1"
            else
                echo "Unknown argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if required arguments are provided
# if [ -z "$RECIPE_FILE" ] || [ -z "$CLUSTER_HOST" ] || [ -z "$REMOTE_PATH" ]; then
#     echo "Usage: $0 <recipe.yaml> <cluster_host> <remote_path> [--no-interactive]"
#     echo "Examples:"
#     echo "  $0 recipes/ollama_meluxina.yaml meluxina /project/home/p200776/team8"
#     echo "  $0 recipes/ollama_meluxina.yaml meluxina /project/home/p200776/team8 --no-interactive"
#     exit 1
# fi

# # Configuration
# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# # ==========================================
# # PHASE 0: Recipe Validation  
# # ==========================================
# echo -e "\n📋 Phase 0: Validating recipe..."
# echo "🔍 Validating recipe: $RECIPE_FILE"

# # Run recipe validation - interactive mode allows user input on warnings
# if [ "$INTERACTIVE_MODE" = true ]; then
#     if ! "$SCRIPT_DIR/../.venv/bin/python" "$SCRIPT_DIR/validate_recipe.py" "$RECIPE_FILE"; then
#         echo "❌ Recipe validation failed. Deployment aborted."
#         exit 1
#     fi
# else
#     if ! "$SCRIPT_DIR/../.venv/bin/python" "$SCRIPT_DIR/validate_recipe.py" "$RECIPE_FILE" --no-interactive; then
#         echo "❌ Recipe validation failed. Deployment aborted."
#         exit 1
#     fi
# fi

# echo "✅ Recipe validation passed"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Test SSH connectivity
test_ssh_connection() {
    local host="$1"
    log_info "Testing SSH connection to $host..."
    
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$host" "echo 'SSH connection successful'" 2>/dev/null; then
        log_success "SSH connection to $host successful"
        return 0
    else
        log_error "SSH connection to $host failed"
        log_error "Please check:"
        log_error "  1. Your SSH key is configured for the cluster"
        log_error "  2. You're connected to the cluster network/VPN"
        log_error "  3. The hostname is correct"
        log_error "  4. Try: ssh $host"
        return 1
    fi
}

# Check if recipe file exists
if [ ! -f "$RECIPE_FILE" ]; then
    log_error "Recipe file not found: $RECIPE_FILE"
    exit 1
fi

# Extract scenario name from recipe
SCENARIO=$(python3 -c "import yaml; print(yaml.safe_load(open('$RECIPE_FILE'))['scenario'])")
SBATCH_FILE="${SCENARIO}_server_only.sh"

log_info "Starting deployment for scenario: $SCENARIO"
log_info "Cluster: $CLUSTER_HOST"
log_info "Remote path: $REMOTE_PATH"

# Test SSH connectivity
if ! test_ssh_connection "$CLUSTER_HOST"; then
    exit 1
fi

################################################################################
# Phase 1: Generate sbatch script
################################################################################

log_info "Phase 1: Generating sbatch script..."

cd "$SCRIPT_DIR/src"

if [ ! -f "generate_sbatch_simple.py" ]; then
    log_error "generate_sbatch_simple.py not found in src directory"
    exit 1
fi

# Generate the sbatch script
python3 generate_sbatch_simple.py "../$RECIPE_FILE" --output "$SBATCH_FILE"

if [ ! -f "$SBATCH_FILE" ]; then
    log_error "Failed to generate sbatch script"
    exit 1
fi

log_success "Generated sbatch script: $SBATCH_FILE"

################################################################################
# Phase 2: Copy files to cluster
################################################################################

log_info "Phase 2: Copying files to cluster..."

# Create remote directory if it doesn't exist
log_info "Creating remote directory structure..."
ssh "$CLUSTER_HOST" "mkdir -p $REMOTE_PATH/benchmark $REMOTE_PATH/logs $REMOTE_PATH/experiments"

# Copy benchmark folder
log_info "Copying benchmark folder..."
if [ -d "benchmark" ]; then
    rsync -avz --delete "benchmark/" "$CLUSTER_HOST:$REMOTE_PATH/benchmark/"
    log_success "Copied benchmark folder"
else
    log_warning "Benchmark folder not found locally, will be created on cluster"
fi

# Copy sbatch script
log_info "Copying sbatch script..."
scp "$SBATCH_FILE" "$CLUSTER_HOST:$REMOTE_PATH/"
log_success "Copied sbatch script"

# Copy recipe file
log_info "Copying recipe file..."
scp "../$RECIPE_FILE" "$CLUSTER_HOST:$REMOTE_PATH/"
log_success "Copied recipe file"

################################################################################
# Phase 3: Submit job
################################################################################

log_info "Phase 3: Submitting job to cluster..."

# Submit the job
JOB_OUTPUT=$(ssh "$CLUSTER_HOST" "cd $REMOTE_PATH && sbatch $SBATCH_FILE")

if [ $? -eq 0 ]; then
    log_success "Job submitted successfully!"
    echo "$JOB_OUTPUT"
    
    # Extract job ID
    JOB_ID=$(echo "$JOB_OUTPUT" | grep -o 'Submitted batch job [0-9]*' | grep -o '[0-9]*')
    
    if [ -n "$JOB_ID" ]; then
        log_info "Job ID: $JOB_ID"
        log_info "Monitor with: ssh $CLUSTER_HOST 'squeue -j $JOB_ID'"
        log_info "View logs: ssh $CLUSTER_HOST 'tail -f $REMOTE_PATH/logs/${SCENARIO}_${JOB_ID}.out'"
        log_info "Cancel job: ssh $CLUSTER_HOST 'scancel $JOB_ID'"
    fi
else
    log_error "Failed to submit job"
    exit 1
fi

################################################################################
# Phase 4: Show monitoring commands
################################################################################

log_info "Phase 4: Monitoring commands"

echo ""
echo "========================================================================"
echo "DEPLOYMENT COMPLETE"
echo "========================================================================"
echo "Scenario:     $SCENARIO"
echo "Cluster:      $CLUSTER_HOST"
echo "Remote path:  $REMOTE_PATH"
echo "Job ID:       $JOB_ID"
echo ""
echo "Useful commands:"
echo "  Monitor job:    ssh $CLUSTER_HOST 'squeue -j $JOB_ID'"
echo "  View logs:      ssh $CLUSTER_HOST 'tail -f $REMOTE_PATH/logs/${SCENARIO}_${JOB_ID}.out'"
echo "  Cancel job:     ssh $CLUSTER_HOST 'scancel $JOB_ID'"
echo "  Check results:  ssh $CLUSTER_HOST 'ls -la $REMOTE_PATH/experiments/'"
echo ""
echo "========================================================================"

log_success "Deployment and job submission completed!"
