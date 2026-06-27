#!/usr/bin/env bash
set -euo pipefail

# Start the metered proxy on localhost:8080 with probe budget {opus:1, haiku:3}.
# PROXY_API_KEY must be set in the outer task environment — it is the real
# Anthropic key the proxy uses to forward author probe requests to api.anthropic.com.
# The grading runs in the step-2 verifier use a separate clean key and bypass
# this proxy entirely (ANTHROPIC_BASE_URL=https://api.anthropic.com in verifier env).

if [[ -z "${PROXY_API_KEY:-}" ]]; then
    echo "ERROR: PROXY_API_KEY is not set — proxy cannot forward to Anthropic." >&2
    exit 1
fi

# Launch proxy in background (app-dir=/opt where proxy.py lives).
PROXY_API_KEY="$PROXY_API_KEY" uvicorn proxy:app \
    --app-dir /opt \
    --host 127.0.0.1 \
    --port 8080 \
    --log-level warning \
    &

# Wait up to 30 s for /health.
echo "Waiting for proxy to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        echo "Metered proxy ready on localhost:8080 (budget: opus=1, haiku=3)."
        rm -- "$0"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Proxy failed to start within 30 s." >&2
exit 1
