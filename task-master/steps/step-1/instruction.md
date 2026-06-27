# Goal 1 — Build a valid, solvable inner task

Read `/app/TARGET.md` first. It specifies the **domain**, the required **verifier
style**, the **difficulty lever**, and the **constraints** your task must satisfy.

Create a Harbor task at **`/app/inner_task/`** that tests the capability described in
`/app/TARGET.md`. It must contain:

- `instruction.md` — the problem statement the *inner* agent will see. The inner agent
  sees **only** this file (never your tests).
- `environment/Dockerfile` — a minimal image suited to the domain.
- `tests/` — a hidden verifier in the style `TARGET.md` requires, writing a **binary**
  reward (`1` on full pass, else `0`) to `/logs/verifier/reward.txt`.
- `solution/` — a reference solution that passes your hidden verifier.

Your task must:

1. **build** — `harbor` can validate and parse it,
2. **pass** — when your reference `solution/` runs, the inner reward is `1.0`,
3. **fail** — when nothing is done (the null agent), the inner reward is `0.0`.

**Do not attempt to make it hard yet.** Difficulty calibration happens in the next step.
Respect every constraint in `/app/TARGET.md` (deterministic, binary reward, no network
at inner runtime, no hardcoded answers, no domain mismatch).
