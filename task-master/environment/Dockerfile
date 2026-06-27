FROM python:3.12-slim

# System deps: curl (probe + health checks), git (harbor may need it)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Harbor CLI with Daytona provider support.
# fastapi, uvicorn, httpx are already in harbor's base deps — no need to repeat.
RUN pip install --no-cache-dir "harbor[daytona]==0.7.1"

# Bake the meta-task config and tools into /opt so they survive workdir uploads.
# NOTE: task.toml is copied from environment/task.toml (a mirror of the root
# task.toml). If you edit [metadata.target], update environment/task.toml and
# rebuild with --force-build.
RUN mkdir -p /opt/meta
COPY task.toml         /opt/meta/task.toml
COPY render_target.py  /opt/render_target.py
COPY proxy.py          /opt/proxy.py

# probe wrapper — available on PATH for the author
COPY probe.sh          /usr/local/bin/probe
RUN chmod +x /usr/local/bin/probe

WORKDIR /app
