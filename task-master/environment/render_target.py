#!/usr/bin/env python3
"""Render the [metadata.target] block of task.toml into a human-readable TARGET.md.

Usage:
    render_target.py <task.toml>                 # write TARGET.md to stdout
    render_target.py <task.toml> --field <name>  # print one [metadata.target] field
"""

import argparse
import sys
import tomllib


def main():
    parser = argparse.ArgumentParser(
        description="Render [metadata.target] from task.toml to TARGET.md or extract a field"
    )
    parser.add_argument("task_toml", help="Path to task.toml")
    parser.add_argument(
        "--field",
        type=str,
        default=None,
        help="Return only the specified [metadata.target] field value",
    )

    args = parser.parse_args()

    # Read and parse task.toml
    try:
        with open(args.task_toml, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        print(f"Error reading {args.task_toml}: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract [metadata.target]
    target = config.get("metadata", {}).get("target", {})

    if not target:
        print("Error: [metadata.target] not found in task.toml", file=sys.stderr)
        sys.exit(1)

    # Handle --field lookup
    if args.field:
        value = target.get(args.field)
        if value is None:
            print(f"Error: field '{args.field}' not found in [metadata.target]", file=sys.stderr)
            sys.exit(1)
        print(value)
        return

    # Render TARGET.md to stdout
    capability = target.get("capability", "")
    domain = target.get("domain", "")
    inner_agent = target.get("inner_agent", "")
    inner_verifier = target.get("inner_verifier", "")
    difficulty_lever = target.get("difficulty_lever", "")
    constraints = target.get("constraints", "")
    forbidden = target.get("forbidden", "")

    output = f"""# Inner Task Target

**Capability:** {capability}
**Domain:** {domain}
**Inner agent:** {inner_agent}
**Inner verifier:** {inner_verifier}
**Difficulty lever:** {difficulty_lever}

## Constraints
{constraints}

## Forbidden
{forbidden}"""
    print(output)


if __name__ == "__main__":
    main()
