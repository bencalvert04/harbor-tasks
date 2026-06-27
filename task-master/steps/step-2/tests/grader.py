#!/usr/bin/env python3
"""Step 2 grader — implements the canonical reward ladder (spec §4).

Inputs (CLI): --build_ok 0|1, --null R, --ref R, --opus R, --haiku R (x2).
Treat a missing/None inner reward as failure (0.0) for that agent.

    build_ok   = inner task builds & parses
    null_fail  = null inner reward == 0.0
    ref_pass   = oracle inner reward == 1.0
    opus_pass  = opus grade inner reward == 1.0
    haiku_fail = both haiku grades == 0.0  (max(h1, h2) < 1.0)

    not build_ok or not null_fail -> 0.00
    not ref_pass                  -> 0.25
    not opus_pass                 -> 0.50
    not haiku_fail                -> 0.75
    else                          -> 1.00

Emits {"reward": R, "null":.., "ref":.., "opus":.., "haiku":[h1,h2]} to stdout.
"""

import argparse
import json
import sys


def coerce_float(value):
    """Convert value to float, treating None or non-numeric as 0.0."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def main():
    parser = argparse.ArgumentParser(
        description="Implement canonical reward ladder from spec §4"
    )
    parser.add_argument("--build_ok", required=True, help="1 if inner task builds")
    parser.add_argument("--null", dest="null_r", help="Null-agent inner reward")
    parser.add_argument("--ref", dest="ref_r", help="Oracle inner reward")
    parser.add_argument("--opus", dest="opus_r", help="Opus grade inner reward")
    parser.add_argument(
        "--haiku",
        action="append",
        dest="haiku_list",
        help="Haiku grade inner reward (can be called twice)",
    )

    args = parser.parse_args()

    # Coerce all values, treating None/missing/"None"/non-numeric as 0.0
    build_ok = (args.build_ok == "1")
    null_r = coerce_float(args.null_r)
    ref_r = coerce_float(args.ref_r)
    opus_r = coerce_float(args.opus_r)

    # Handle haiku list: up to 2 values, pad with 0.0 if needed
    haiku_list = args.haiku_list if args.haiku_list else []
    h1 = coerce_float(haiku_list[0]) if len(haiku_list) > 0 else 0.0
    h2 = coerce_float(haiku_list[1]) if len(haiku_list) > 1 else 0.0

    # Implement §4 ladder
    null_fail = null_r == 0.0
    ref_pass = ref_r == 1.0
    opus_pass = opus_r == 1.0
    haiku_fail = max(h1, h2) < 1.0

    if not build_ok or not null_fail:
        reward = 0.0
    elif not ref_pass:
        reward = 0.25
    elif not opus_pass:
        reward = 0.50
    elif not haiku_fail:
        reward = 0.75
    else:
        reward = 1.0

    # Emit JSON to stdout
    output = {
        "reward": reward,
        "null": null_r,
        "ref": ref_r,
        "opus": opus_r,
        "haiku": [h1, h2],
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
