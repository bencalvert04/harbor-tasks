#!/bin/bash
# Runs in the agent container (shared verifier mode) after the agent finishes.
# Grades against the read-only tool service log at /srv/tool-log/requests.ndjson.

set -u

pip install --quiet --no-cache-dir pytest==8.4.1

python -m pytest /tests/test_outputs.py -rA \
  --junit-xml=/logs/verifier/junit.xml

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
