Note from Ben: Claude did this entire thing. More of a proof of concept and walkthrough than anything.

# bencalvert/solid-bg-removal

## What the agent does

The agent is given a folder of `.png` photos, each showing one or more foreground
objects on a **single solid-color studio backdrop** (the background color varies
between photos). It must write a program that removes the background from every
photo and saves an RGBA PNG — background fully transparent, foreground opaque — to
`/app/output/` using the same filename. See [`instruction.md`](instruction.md) for
the exact prompt the agent receives.

The task is scoped to *solid-color* backgrounds on purpose: this keeps grading
fully deterministic (a known foreground/background) while still being a real,
useful feature (product / studio photo cutouts).

## Environment

- Base image: `python:3.12-slim-bookworm`.
- Pre-installed: `pillow==12.2.0`, `numpy==2.4.4` (tools, not a solution).
- Input photos baked in at `/app/input/` (5 images, 256×256, anti-aliased edges,
  varied background colors: white, chroma green, gray, blue, beige).
- 1 CPU, 2 GB RAM. Agent timeout: 600 s.

## Verifier

`pytest` (deterministic). For each photo, the verifier derives a binary
foreground mask from the agent output's **alpha channel** (`alpha >= 128`) and
compares it to a hidden ground-truth mask via **Intersection-over-Union**.

| Check | Type | What it measures |
| --- | --- | --- |
| `test_masks_present` | programmatic | Ground-truth masks exist (verifier sanity) |
| `test_background_removed[<image>]` | programmatic | Output exists, is RGBA, matches input size, has transparent pixels, and IoU ≥ 0.92 against the ground-truth mask |

All checks must pass for reward `1`; otherwise `0` (written to
`/logs/verifier/reward.txt`). Ground-truth masks live in `tests/masks/` and are
**never** shown to the agent — they are only uploaded into the verifier at grading
time. The reference solution scores a worst-case IoU of ~0.98.

## Layout

```
solid-bg-removal/
├── instruction.md            # Prompt shown to the agent
├── task.toml                 # Config + metadata
├── generate_data.py          # Regenerates inputs + masks deterministically (dev only)
├── environment/
│   ├── Dockerfile            # python:3.12-slim + pillow/numpy, copies input/
│   └── input/*.png           # The 5 photos baked into the image
├── solution/
│   └── solve.sh              # Reference solver (corner-sample bg + distance threshold)
└── tests/
    ├── test.sh               # Installs deps, runs pytest, writes reward.txt
    ├── test_outputs.py       # IoU verifier
    └── masks/*.png           # Hidden ground-truth foreground masks
```

## Regenerating the dataset

```bash
python3 generate_data.py   # writes environment/input/*.png and tests/masks/*.png
```

Deterministic — fixed seeds and shapes, so output is byte-stable.

## Running

```bash
# Sanity-check that the task is solvable and the verifier passes (expect reward 1.0)
harbor run -p solid-bg-removal -a oracle

# Try a real agent
harbor run -p solid-bg-removal -a terminus-2 -m anthropic/claude-sonnet-4-6
```
