#!/bin/bash
# probe — run the inner task against a model, consuming one lease from the metered proxy.
#
# Usage:
#   probe --model haiku    (up to 3 runs)
#   probe --model opus     (up to 1 run)
#
# The proxy on localhost:8080 enforces the budget. Calls beyond the limit are
# rejected with a clear message. Grading runs are reserved separately and are
# independent of this budget.

set -euo pipefail

usage() {
    echo "Usage: probe --model haiku|opus" >&2
    exit 1
}

MODEL=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="${2:-}"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown argument: $1" >&2; usage ;;
    esac
done
[[ -z "$MODEL" ]] && usage

case "$MODEL" in
    haiku) FULL_MODEL="anthropic/claude-haiku-4-5-20251001" ;;
    opus)  FULL_MODEL="anthropic/claude-opus-4-6" ;;
    *)     echo "Unknown model '$MODEL'. Use 'haiku' or 'opus'." >&2; exit 1 ;;
esac

# Lease a one-time run token from the metered proxy.
LEASE_RESP=$(curl -sf http://localhost:8080/lease \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$FULL_MODEL\"}" 2>&1) || {
    echo "Probe budget exhausted for $MODEL — no runs remaining." >&2
    exit 1
}

TOKEN=$(echo "$LEASE_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
REMAINING=$(echo "$LEASE_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['remaining'])")
echo "[$MODEL probe] token issued. $MODEL runs remaining after this: $REMAINING"

# Read inner_agent from baked task config.
AGENT=$(python3 /opt/render_target.py /opt/meta/task.toml --field inner_agent)

PROBE_DIR=$(mktemp -d /tmp/probe-XXXXXX)

# Run the inner task with the leased token as the API key.
# ANTHROPIC_BASE_URL is already set to the proxy (localhost:8080) in the env.
ANTHROPIC_API_KEY="$TOKEN" harbor run \
    -p /app/inner_task \
    -a "$AGENT" \
    -m "$FULL_MODEL" \
    -e "${HARBOR_PROVIDER:-daytona}" \
    --jobs-dir "$PROBE_DIR" \
    -y

# Print reward.
python3 - "$PROBE_DIR" << 'PY'
import json, glob, sys
files = glob.glob(sys.argv[1] + "/*/result.json")
if not files:
    print("[probe] No result.json found — run may have failed.")
    sys.exit(0)
data = json.load(open(files[0]))
vr = data.get("verifier_result") or {}
reward = vr.get("rewards", {}).get("reward", "N/A")
exc = data.get("exception_info")
print(f"\n[probe] reward = {reward}")
if exc:
    print(f"[probe] exception: {exc}")
PY

rm -rf "$PROBE_DIR"
