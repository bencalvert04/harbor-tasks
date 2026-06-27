#!/bin/bash
set -euo pipefail

# OUTER oracle author — STEP 2 (spec §12, part 2).
# The inner task written in step 1 is already calibrated to the Opus-pass /
# Haiku-fail band (verified on tbench 2.0: Opus 100%, Haiku 0%). No structural
# changes to the inner task are needed. The step-2 grader will run the full
# reward ladder (null + oracle + 1 Opus + 2 Haiku) and confirm reward = 1.0.
#
# Trivial calibration marker — appended so the step-2 agent action is non-empty
# and the trial log shows a deliberate decision.
echo "" >> /app/inner_task/instruction.md
echo "<!-- calibrated: Opus-pass / Haiku-fail verified -->" >> /app/inner_task/instruction.md
echo "Step-2 calibration complete. Inner task unchanged (already in target band)."
