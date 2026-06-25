"""Generate the synthetic dataset for the solid-bg-removal task.

Produces, for each sample:
  - environment/input/<name>.png : an RGB "photo" of foreground shapes over a
    single solid background color, with anti-aliased edges (supersampled).
  - tests/masks/<name>.png        : a binary ground-truth mask (255 = foreground,
    0 = background) used by the verifier to score the agent's alpha channel.

Run from the task root:  python3 generate_data.py
The output is deterministic (fixed seeds), so regenerating gives identical files.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw

W = H = 256
SS = 4  # supersampling factor for anti-aliased edges

ROOT = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(ROOT, "environment", "input")
MASK_DIR = os.path.join(ROOT, "tests", "masks")


def _draw_shapes(draw: ImageDraw.ImageDraw, shapes: list, fill) -> None:
    """Draw each shape (in supersampled coords) onto draw with the given fill."""
    for kind, coords in shapes:
        if kind == "ellipse":
            draw.ellipse(coords, fill=fill)
        elif kind == "rectangle":
            draw.rectangle(coords, fill=fill)
        elif kind == "polygon":
            draw.polygon(coords, fill=fill)
        else:
            raise ValueError(f"unknown shape: {kind}")


def make_sample(name: str, bg_color, shapes: list) -> None:
    """Render one photo + mask. `shapes` is a list of (kind, coords, color)."""
    big = (W * SS, H * SS)

    # Coverage layer: 255 where any foreground shape is, 0 elsewhere.
    cov = Image.new("L", big, 0)
    cov_draw = ImageDraw.Draw(cov)

    # Foreground color layer (only meaningful where covered).
    fg = Image.new("RGB", big, (0, 0, 0))
    fg_draw = ImageDraw.Draw(fg)

    for kind, coords, color in shapes:
        ss_coords = _scale_coords(kind, coords)
        _draw_shapes(cov_draw, [(kind, ss_coords)], 255)
        _draw_shapes(fg_draw, [(kind, ss_coords)], color)

    cov_small = cov.resize((W, H), Image.LANCZOS)
    fg_small = fg.resize((W, H), Image.LANCZOS)

    alpha = np.asarray(cov_small, dtype=np.float32) / 255.0
    fg_arr = np.asarray(fg_small, dtype=np.float32)
    bg_arr = np.asarray(Image.new("RGB", (W, H), bg_color), dtype=np.float32)

    comp = fg_arr * alpha[..., None] + bg_arr * (1.0 - alpha[..., None])
    photo = Image.fromarray(np.clip(comp.round(), 0, 255).astype(np.uint8), "RGB")

    mask_arr = (np.asarray(cov_small) >= 128).astype(np.uint8) * 255
    mask = Image.fromarray(mask_arr, "L")

    photo.save(os.path.join(INPUT_DIR, f"{name}.png"))
    mask.save(os.path.join(MASK_DIR, f"{name}.png"))


def _scale_coords(kind: str, coords):
    if kind == "polygon":
        return [(x * SS, y * SS) for (x, y) in coords]
    return [c * SS for c in coords]


SAMPLES = [
    # name, bg_color, [(kind, coords, color), ...]
    (
        "studio_white",
        (255, 255, 255),
        [("ellipse", (60, 50, 200, 210), (40, 90, 180))],
    ),
    (
        "chroma_green",
        (0, 177, 64),
        [
            ("rectangle", (70, 60, 190, 200), (200, 40, 40)),
            ("ellipse", (110, 30, 150, 70), (240, 220, 60)),
        ],
    ),
    (
        "gray_seamless",
        (210, 210, 210),
        [("polygon", [(128, 30), (220, 220), (36, 220)], (60, 60, 70))],
    ),
    (
        "blue_backdrop",
        (30, 80, 160),
        [
            ("ellipse", (40, 90, 130, 180), (235, 180, 40)),
            ("ellipse", (130, 70, 215, 160), (235, 120, 40)),
        ],
    ),
    (
        "beige_table",
        (224, 210, 178),
        [
            ("rectangle", (50, 120, 206, 205), (120, 70, 40)),
            ("polygon", [(128, 45), (175, 125), (81, 125)], (40, 110, 90)),
        ],
    ),
]


def main() -> None:
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)
    for name, bg_color, shapes in SAMPLES:
        make_sample(name, bg_color, shapes)
        print(f"wrote {name}")
    print(f"\n{len(SAMPLES)} samples -> {INPUT_DIR} and {MASK_DIR}")


if __name__ == "__main__":
    main()
