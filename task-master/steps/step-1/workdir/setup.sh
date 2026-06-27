#!/usr/bin/env bash
set -euo pipefail

# Render /app/TARGET.md from the baked [metadata.target] block so the author
# reads a single source of truth about the domain, verifier style, and constraints.
python3 /opt/render_target.py /opt/meta/task.toml > /app/TARGET.md

echo "TARGET.md written to /app/TARGET.md"

# Self-delete so this script isn't left in WORKDIR for the agent to find.
rm -- "$0"
