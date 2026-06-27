#!/bin/bash
# Reward Kit runs checks.py (structural) + judge.toml (LLM judge) over /tests,
# grading /app/skill.md and writing /logs/verifier/reward.json.
# The judge needs ANTHROPIC_API_KEY (or CLAUDE_CODE_OAUTH_TOKEN) — see
# [verifier.env] in task.toml.

# The agent environment (ubuntu:24.04) has no uv/uvx, so install it here. curl +
# ca-certificates come from environment/Dockerfile; this needs network at verify
# time (allow_internet = true).
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
source "$HOME/.local/bin/env"

uvx --from 'harbor-rewardkit==0.1.*' rewardkit /tests
