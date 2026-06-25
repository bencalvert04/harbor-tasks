"""Verifier for solid-bg-removal.

For each ground-truth mask in /tests/masks/, find the agent's corresponding
output in /app/output/, derive a binary foreground mask from its alpha channel,
and require the Intersection-over-Union against the ground truth to clear a
threshold. Deterministic: same outputs -> same pass/fail.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

OUTPUT_DIR = Path("/app/output")
MASK_DIR = Path("/tests/masks")

# Per-image IoU required to count as correct. Anti-aliased edge pixels make a
# perfect 1.0 impossible; 0.92 is comfortably above any reasonable approach yet
# well below what a correct solid-color remover achieves (~0.99).
IOU_THRESHOLD = 0.92

# alpha >= this counts as foreground.
ALPHA_CUTOFF = 128

MASKS = sorted(MASK_DIR.glob("*.png"))


def _binary(arr: np.ndarray) -> np.ndarray:
    return arr >= ALPHA_CUTOFF


def _iou(pred: np.ndarray, gt: np.ndarray) -> float:
    inter = np.logical_and(pred, gt).sum()
    union = np.logical_or(pred, gt).sum()
    return 1.0 if union == 0 else float(inter) / float(union)


def test_masks_present():
    """Sanity check: the verifier actually has ground-truth masks to grade."""
    assert MASKS, f"no ground-truth masks found in {MASK_DIR}"


@pytest.mark.parametrize("mask_path", MASKS, ids=lambda p: p.stem)
def test_background_removed(mask_path: Path):
    out_path = OUTPUT_DIR / mask_path.name
    assert out_path.exists(), f"missing output for {mask_path.name} at {out_path}"

    out_img = Image.open(out_path)
    assert "A" in out_img.getbands(), (
        f"{out_path.name} has no alpha channel (bands={out_img.getbands()}); "
        "output must be RGBA with the background transparent"
    )

    gt = np.asarray(Image.open(mask_path).convert("L"))
    out_rgba = out_img.convert("RGBA")
    assert out_rgba.size == (gt.shape[1], gt.shape[0]), (
        f"{out_path.name} size {out_rgba.size} != input size "
        f"{(gt.shape[1], gt.shape[0])}"
    )

    alpha = np.asarray(out_rgba)[..., 3]

    # The background must actually become transparent somewhere — guards against
    # an agent that just copies the input through as fully-opaque RGBA.
    assert (alpha < ALPHA_CUTOFF).any(), (
        f"{out_path.name} has no transparent pixels; background was not removed"
    )

    iou = _iou(_binary(alpha), _binary(gt))
    assert iou >= IOU_THRESHOLD, (
        f"{out_path.name}: foreground IoU {iou:.3f} < {IOU_THRESHOLD}"
    )
