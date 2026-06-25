#!/bin/bash
set -euo pipefail

# Reference solution: infer the solid background color from the image corners,
# then make every pixel close to that color transparent. Outputs RGBA PNGs.

mkdir -p /app/output

python3 - <<'PY'
import os
from pathlib import Path

import numpy as np
from PIL import Image

INPUT = Path("/app/input")
OUTPUT = Path("/app/output")
OUTPUT.mkdir(parents=True, exist_ok=True)

# Distance (in RGB Euclidean space) above which a pixel counts as foreground.
THRESHOLD = 60.0

for path in sorted(INPUT.glob("*.png")):
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    h, w, _ = arr.shape

    # Background color = median of the four corner pixels (corners are backdrop).
    corners = np.stack([arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1]])
    bg = np.median(corners, axis=0)

    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    alpha = np.where(dist > THRESHOLD, 255, 0).astype(np.uint8)

    rgba = np.dstack([arr.astype(np.uint8), alpha])
    Image.fromarray(rgba, "RGBA").save(OUTPUT / path.name)
    print(f"wrote {OUTPUT / path.name}")
PY
