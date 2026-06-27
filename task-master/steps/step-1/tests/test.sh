#!/bin/bash
set -uo pipefail

# Step 1 verifier — free checks only, no model tokens.
# Emits {"reward": R} where R in {0.00, 0.25, 0.50}.
#   0.00 = inner task doesn't build/parse, OR null agent doesn't fail
#   0.25 = builds + null fails, but oracle doesn't pass (not solvable)
#   0.50 = builds + null fails + oracle passes → proceed to step 2
#
# min_reward = 0.5 in task.toml gates on the "reward" key here.

INNER=/app/inner_task
JOBS=/tmp/inner-run-$$
mkdir -p "$JOBS"

R=0.0
null_r=0.0
ref_r=0.0

# Extract reward from a harbor run jobs dir (reads the single trial result.json).
get_reward() {
    local dir="$1"
    python3 - "$dir" << 'PY'
import json, glob, sys
files = glob.glob(sys.argv[1] + "/*/result.json")
if not files:
    print("0.0"); sys.exit(0)
data = json.load(open(files[0]))
vr = data.get("verifier_result") or {}
print(vr.get("rewards", {}).get("reward", 0.0))
PY
}

# 1. Build/parse check — no harbor validate command; parse TaskConfig directly.
if python3 -c "
from harbor.models.task.config import TaskConfig
TaskConfig.model_validate_toml(open('$INNER/task.toml').read())
" 2>/logs/verifier/build_check.log; then

    # 2. Null agent (nop) must score 0.0 — task must be fail-able.
    harbor run -p "$INNER" -a nop \
        -e "${HARBOR_PROVIDER:-docker}" \
        --jobs-dir "$JOBS/null" -y -q \
        2>/logs/verifier/null_run.log || true
    null_r=$(get_reward "$JOBS/null")

    if [ "$(python3 -c "print('1' if float('${null_r}') == 0.0 else '0')")" = "1" ]; then
        R=0.25

        # 3. Oracle (reference solution) must score 1.0 — task must be solvable.
        harbor run -p "$INNER" -a oracle \
            -e "${HARBOR_PROVIDER:-docker}" \
            --jobs-dir "$JOBS/oracle" -y -q \
            2>/logs/verifier/oracle_run.log || true
        ref_r=$(get_reward "$JOBS/oracle")

        if [ "$(python3 -c "print('1' if float('${ref_r}') == 1.0 else '0')")" = "1" ]; then
            R=0.5
        fi
    fi
fi

python3 -c "
import json
print(json.dumps({'reward': $R, 'null': $null_r, 'ref': $ref_r}))
" > /logs/verifier/reward.json

rm -rf "$JOBS"
