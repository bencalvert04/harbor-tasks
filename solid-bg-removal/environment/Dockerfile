FROM python:3.12-slim-bookworm

WORKDIR /app

# Libraries the agent may use to read/write images. Not a solution — just tools.
RUN pip install --no-cache-dir pillow==12.2.0 numpy==2.4.4

# The photos to process. The agent writes results to /app/output/.
COPY input/ /app/input/
