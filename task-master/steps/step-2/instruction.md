# Goal 2 — Calibrate difficulty (Haiku fails, Opus still passes)

Your inner task at `/app/inner_task/` already builds and is solvable. Now make it
**hard enough that Haiku 4.5 fails it, without breaking solvability** — Opus 4.8 must
still pass it from the instruction alone.

Strengthen the spec and add edge-case tests (the `difficulty_lever` from
`/app/TARGET.md`) that a weak model tends to drop, **while your reference solution still
passes**. Do not break the contract: the inner agent still sees only `instruction.md`,
the reward stays binary and deterministic, and there is no network at inner runtime.

You may **probe** to see where the difficulty lands. Each probe runs your task against a
real model in a sandbox and shows you the reward and the inner agent's transcript:

```
probe --model haiku    # up to 3 runs
probe --model opus     # up to 1 run
```

The budget is enforced; calls beyond it are rejected. The grade runs (which you never
see) are reserved separately. Edit `/app/inner_task/` and submit when ready.
