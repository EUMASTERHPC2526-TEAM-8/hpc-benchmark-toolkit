#!/bin/bash


set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
EXPERIMENT_DIR="${1:-}"

if [ -z "$EXPERIMENT_DIR" ]; then
    echo -e "${RED}Usage: $0 <experiment_directory>${NC}"
    echo "Example: $0 experiments/logging-test_20251228_123456"
    exit 1
fi

if [ ! -d "$EXPERIMENT_DIR" ]; then
    echo -e "${RED}Error: Directory not found: $EXPERIMENT_DIR${NC}"
    exit 1
fi

echo "========================================================================"
echo -e "${BLUE}LOGGING COMPONENT VALIDATION${NC}"
echo "========================================================================"
echo "Experiment: $EXPERIMENT_DIR"
echo ""

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "[$TOTAL_TESTS] Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN} PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED} FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test function with output
run_test_with_output() {
    local test_name="$1"
    local test_command="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "[$TOTAL_TESTS] Testing: $test_name..."
    
    if eval "$test_command"; then
        echo -e "${GREEN} PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED} FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "========================================================================"
echo "FILE EXISTENCE TESTS"
echo "========================================================================"

# Test 1: Check stdout.log exists
run_test "stdout.log exists" "[ -f '$EXPERIMENT_DIR/stdout.log' ]"

# Test 2: Check stderr.log exists
run_test "stderr.log exists" "[ -f '$EXPERIMENT_DIR/stderr.log' ]"

# Test 3: Check aggregated.jsonl exists
run_test "aggregated.jsonl exists" "[ -f '$EXPERIMENT_DIR/aggregated.jsonl' ]"

# Test 4: Check loggers_ready flag was created
run_test "loggers_ready flag exists" "[ -f '$EXPERIMENT_DIR/loggers_ready' ]"

echo ""
echo "========================================================================"
echo "FILE SIZE TESTS"
echo "========================================================================"

# Test 5: stdout.log is not empty
run_test "stdout.log has content" "[ -s '$EXPERIMENT_DIR/stdout.log' ]"

# Test 6: aggregated.jsonl is not empty
run_test "aggregated.jsonl has content" "[ -s '$EXPERIMENT_DIR/aggregated.jsonl' ]"

# Test 7: stderr.log should be empty or small (no errors expected)
if [ -f "$EXPERIMENT_DIR/stderr.log" ]; then
    STDERR_SIZE=$(wc -c < "$EXPERIMENT_DIR/stderr.log")
    if [ "$STDERR_SIZE" -eq 0 ]; then
        echo "[$TOTAL_TESTS] Testing: stderr.log is empty (no errors)... ${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
    else
        echo "[$TOTAL_TESTS] Testing: stderr.log is empty (no errors)... ${YELLOW}⚠ WARNING${NC} (size: $STDERR_SIZE bytes)"
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
    fi
fi

echo ""
echo "========================================================================"
echo "CONTENT VALIDATION TESTS"
echo "========================================================================"

# Test 8: Count lines in stdout.log
STDOUT_LINES=$(wc -l < "$EXPERIMENT_DIR/stdout.log")
echo "[$TOTAL_TESTS] Testing: stdout.log line count (>50 expected)..."
echo "   Lines: $STDOUT_LINES"
if [ "$STDOUT_LINES" -gt 50 ]; then
    echo -e "   ${GREEN} PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} (too few lines)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 9: Count lines in aggregated.jsonl
JSONL_LINES=$(wc -l < "$EXPERIMENT_DIR/aggregated.jsonl")
echo "[$TOTAL_TESTS] Testing: aggregated.jsonl line count (>50 expected)..."
echo "   Lines: $JSONL_LINES"
if [ "$JSONL_LINES" -gt 50 ]; then
    echo -e "   ${GREEN} PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} (too few lines)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 10: Verify stdout.log and jsonl have similar line counts
echo "[$TOTAL_TESTS] Testing: stdout and jsonl line counts match..."
DIFF=$((STDOUT_LINES - JSONL_LINES))
DIFF=${DIFF#-}  # Absolute value
echo "   stdout: $STDOUT_LINES, jsonl: $JSONL_LINES, diff: $DIFF"
if [ "$DIFF" -lt 5 ]; then
    echo -e "   ${GREEN} PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${YELLOW} WARNING${NC} (line count mismatch)"
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 11: Check log format in stdout.log
echo "[$TOTAL_TESTS] Testing: stdout.log format (timestamp, node, component)..."
SAMPLE_LINE=$(head -1 "$EXPERIMENT_DIR/stdout.log")
echo "   Sample: $SAMPLE_LINE"
if echo "$SAMPLE_LINE" | grep -qE '^\[20[0-9]{2}-[0-9]{2}-[0-9]{2}T.*\] \[.*\] \[.*\]'; then
    echo -e "   ${GREEN} PASS${NC} (correct format)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} (incorrect format)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 12: Validate JSON format
echo "[$TOTAL_TESTS] Testing: aggregated.jsonl JSON validity..."
INVALID_JSON=0
while IFS= read -r line; do
    if ! echo "$line" | python3 -m json.tool > /dev/null 2>&1; then
        INVALID_JSON=$((INVALID_JSON + 1))
    fi
done < "$EXPERIMENT_DIR/aggregated.jsonl"

if [ "$INVALID_JSON" -eq 0 ]; then
    echo -e "   ${GREEN} PASS${NC} (all $JSONL_LINES lines are valid JSON)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} ($INVALID_JSON invalid JSON lines)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

echo ""
echo "========================================================================"
echo "MULTI-NODE AGGREGATION TESTS"
echo "========================================================================"

# Test 13: Check for multiple nodes in logs
echo "[$TOTAL_TESTS] Testing: logs from multiple nodes..."
NODES=$(python3 -c "
import json
nodes = set()
with open('$EXPERIMENT_DIR/aggregated.jsonl') as f:
    for line in f:
        log = json.loads(line)
        nodes.add(log.get('node', 'unknown'))
print(len(nodes), ','.join(sorted(nodes)))
")
NODE_COUNT=$(echo "$NODES" | cut -d' ' -f1)
NODE_LIST=$(echo "$NODES" | cut -d' ' -f2)

echo "   Nodes found: $NODE_COUNT ($NODE_LIST)"
if [ "$NODE_COUNT" -ge 2 ]; then
    echo -e "   ${GREEN} PASS${NC} (multi-node aggregation working)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} (expected ≥2 nodes, got $NODE_COUNT)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 14: Check for both server and client components
echo "[$TOTAL_TESTS] Testing: logs from server and client components..."
COMPONENTS=$(python3 -c "
import json
components = set()
with open('$EXPERIMENT_DIR/aggregated.jsonl') as f:
    for line in f:
        log = json.loads(line)
        components.add(log.get('component', 'unknown'))
print(','.join(sorted(components)))
")

echo "   Components found: $COMPONENTS"
if echo "$COMPONENTS" | grep -q "server" && echo "$COMPONENTS" | grep -q "client"; then
    echo -e "   ${GREEN} PASS${NC} (both server and client logs present)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "   ${RED} FAIL${NC} (missing server or client logs)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 15: Check log distribution
echo "[$TOTAL_TESTS] Testing: log distribution across components..."
python3 << 'EOF'
import json
from collections import Counter

components = Counter()
with open('$EXPERIMENT_DIR/aggregated.jsonl') as f:
    for line in f:
        log = json.loads(line)
        components[log.get('component', 'unknown')] += 1

print("   Distribution:")
for comp, count in sorted(components.items()):
    print(f"     {comp}: {count} logs")
EOF
echo -e "   ${GREEN} INFO${NC}"

echo ""
echo "========================================================================"
echo "ANALYSIS TOOL TEST"
echo "========================================================================"

# Test 16: Run analyze_logs.py if available
if [ -f "analyze_logs.py" ]; then
    echo "[$TOTAL_TESTS] Testing: analyze_logs.py execution..."
    if python3 analyze_logs.py "$EXPERIMENT_DIR/aggregated.jsonl" > "$EXPERIMENT_DIR/analysis_report.txt" 2>&1; then
        echo -e "   ${GREEN} PASS${NC}"
        echo "   Report saved to: $EXPERIMENT_DIR/analysis_report.txt"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "   ${RED} FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
else
    echo "[$TOTAL_TESTS] Skipping: analyze_logs.py not found"
fi

echo ""
echo "========================================================================"
echo "SAMPLE OUTPUT"
echo "========================================================================"

echo -e "${BLUE}First 10 lines from stdout.log:${NC}"
head -10 "$EXPERIMENT_DIR/stdout.log" | sed 's/^/  /'

echo ""
echo -e "${BLUE}Sample JSON entry from aggregated.jsonl:${NC}"
head -1 "$EXPERIMENT_DIR/aggregated.jsonl" | python3 -m json.tool | sed 's/^/  /'

echo ""
echo "========================================================================"
echo "TEST SUMMARY"
echo "========================================================================"
echo "Total tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:${NC}       $TESTS_PASSED"
echo -e "${RED}Failed:${NC}       $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD} ALL TESTS PASSED!${NC}"
    echo ""
    echo "logging component is working correctly on MeluXina"
    exit 0
else
    echo -e "${RED}${BOLD} SOME TESTS FAILED${NC}"
    echo ""
    echo "Please review the failed tests above."
    exit 1
fi