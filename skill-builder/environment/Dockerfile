FROM ubuntu:24.04

# Install or copy over any environment dependencies here.

WORKDIR /app

# Avoid interactive prompts during apt installs.
ENV DEBIAN_FRONTEND=noninteractive

# Client tools so the agent can make use of the internet access granted by
# `allow_internet = true` in task.toml (ca-certificates + curl for HTTPS
# fetches, git for cloning the Harbor repo to read the real task.toml schema).
# The verifier (tests/test.sh) installs its own deps — curl, uv, pytest — at
# verify time, so those are intentionally not baked in here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*