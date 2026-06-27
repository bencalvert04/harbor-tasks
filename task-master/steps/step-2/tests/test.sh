#!/bin/bash
set -uo pipefail

# Step 2 verifier — re-derives the FULL §4 reward ladder, spending model tokens.
# Runs with the CLEAN grading key from [steps.verifier.env] (ANTHROPIC_API_KEY,
# ANTHROPIC_BASE_URL) — independent of the author's proxy probe budget.
# Emits {"reward": R} where R in {0.50, 0.75, 1.00}.

INNER=/app/inner_task
JOBS=/tmp/grade-run-$$
mkdir -p "$JOBS"

# Inner agent is read from [metadata.target].inner_agent (baked into the image).
AGENT=$(python3 /opt/render_target.py /opt/meta/task.toml --field inner_agent)

# Extract reward from a harbor run jobs dir.
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

PROVIDER="${HARBOR_PROVIDER:-docker}"
RUN="harbor run -p $INNER -e $PROVIDER --jobs-dir"

# Free checks (re-run in case author regressed solvability in step 2).
build_ok=0
python3 -c "
from harbor.models.task.config import TaskConfig
TaskConfig.model_validate_toml(open('$INNER/task.toml').read())
" 2>/logs/verifier/build_check.log && build_ok=1

$RUN "$JOBS/null"    -a nop    -y -q 2>/logs/verifier/null_run.log    || true
$RUN "$JOBS/oracle"  -a oracle -y -q 2>/logs/verifier/oracle_run.log  || true
null_r=$(get_reward "$JOBS/null")
ref_r=$(get_reward  "$JOBS/oracle")

# Grade runs — 1 Opus + 2 Haiku (uses the clean ANTHROPIC_API_KEY from verifier env).
$RUN "$JOBS/opus" \
    -a "$AGENT" -m "anthropic/claude-opus-4-6" \
    -y -q 2>/logs/verifier/opus_run.log || true

$RUN "$JOBS/haiku1" \
    -a "$AGENT" -m "anthropic/claude-haiku-4-5-20251001" \
    -y -q 2>/logs/verifier/haiku1_run.log || true

$RUN "$JOBS/haiku2" \
    -a "$AGENT" -m "anthropic/claude-haiku-4-5-20251001" \
    -y -q 2>/logs/verifier/haiku2_run.log || true

opus_r=$(get_reward  "$JOBS/opus")
h1=$(get_reward      "$JOBS/haiku1")
h2=$(get_reward      "$JOBS/haiku2")

# Compute the §4 ladder and write reward.json.
python3 /tests/grader.py \
    --build_ok "$build_ok" \
    --null     "$null_r" \
    --ref      "$ref_r" \
    --opus     "$opus_r" \
    --haiku    "$h1" \
    --haiku    "$h2" \
    > /logs/verifier/reward.json

rm -rf "$JOBS"
