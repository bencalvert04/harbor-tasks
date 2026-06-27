# Harbor Meta-Task Spec — "Author a calibrated task"

**Build target:** a multi-step Harbor task that tests whether an *agent* can author a
second Harbor task that is **solvable, hard for a weak model, and passable by a strong
model**. The agent under test is the *author*. We grade the author.

This document is written to be handed to Claude Code as the build spec. Suggested kickoff
prompt: *"Read harbor-meta-task-spec.md. Scaffold the task with `harbor init`, then
implement it section by section, starting with the metered proxy and the inner-task
contract. Stop after each milestone in §13 so I can run the oracle check."*

Schemas below were taken from the current Harbor docs (`/docs/tasks`, `/docs/tasks/multi-step`).
Anything I wasn't certain about is flagged in §14 — confirm those against your installed
Harbor version before relying on them.

---

## 1. Mental model: two levels

There are two nested levels. Keep them straight; almost every bug here is a level confusion.

- **OUTER task** = this meta-task. The agent under test is the **author**. Its reward (0.0–1.0)
  is what this whole repo computes.
- **INNER task** = the small Harbor task the author *builds* inside the container. It is run
  against four "agents": a **reference solution** (oracle, free), a **null** agent (free),
  **Opus 4.8**, and **Haiku 4.5**.

The author never grades anything. The OUTER verifier runs the INNER task through those four
agents and derives the author's reward mechanically. No LLM judge anywhere in the reward path.

---

## 2. The core insight (why this is honest, not subjective)

Requiring **Opus to pass** does double duty:

1. **It is the solvability proof.** The author controls both the inner task *and* its
   reference solution, so "reference passes" only proves the author wrote a verifier its own
   answer satisfies — not that the instruction is followable by anyone else. Opus sees only
   the instruction. If Opus passes, a real path from instruction → solution provably exists.
   This kills the "rig a vague/impossible task so the weak model fails" cheat for free.
2. **It pins the difficulty band.** Full credit requires Opus passes **and** Haiku fails, so
   the task must land in the gap between two real models: too hard for Haiku, within reach for
   Opus. That is the "populated interval" — its edges defined by models, not asserted.

The reference solution's job therefore shrinks to a **free pre-filter** (oracle runs cost no
tokens): check `reference passes + null fails` before spending any Opus/Haiku budget.

---

## 3. Locked decisions

| Decision | Value |
|---|---|
| Inner capability X | **Set by the editable `[metadata.target]` block in `task.toml` (§6a).** Choose the domain (coding / mathematics / computer use / data analysis / custom), the inner verifier style, and the difficulty lever. Coding-with-`pytest` is the worked default below. |
| Authoring mode | Open — author writes the entire inner task, reference solution included. (Safe because Opus-passing is the solvability check.) |
| Opus budget | 2 runs total: **1 probe** (author may run during calibration) + **1 grade** (verifier, author can't touch). Model: `anthropic/claude-opus-4-8`. |
| Haiku budget | 5 runs total: **3 probes** + **2 grades**. Model: `anthropic/claude-haiku-4-5-20251001`. |
| "Opus passes" | inner reward == 1.0 on its single grade run. |
| "Haiku fails" | inner reward == 0.0 on **both** grade runs. |
| Reward strategy | `multi_step_reward_strategy = "final"`. |
| Inner runtime | remote sandbox provider (Daytona or Modal), **not** Docker-in-Docker. See §11. |

---

## 4. Canonical reward (computed in the step-2 verifier)

Monotonic ladder. Difficulty credit is **gated on solvability** — you cannot reach 0.75/1.0
without Opus passing, so wrecking the task to defeat Haiku earns nothing.

```
build_ok    = inner task builds & parses
null_fail   = null-agent inner reward == 0.0
ref_pass    = oracle (reference solution) inner reward == 1.0
opus_pass   = opus grade inner reward == 1.0
haiku_fail  = both haiku grade inner rewards == 0.0   # max(two runs) < 1.0

if   not build_ok or not null_fail: R = 0.00   # no valid/fail-able task
elif not ref_pass:                  R = 0.25   # builds + null fails, but not solvable
elif not opus_pass:                 R = 0.50   # solvable by reference, but not from instruction (or author broke it)
elif not haiku_fail:                R = 0.75   # solvable + Opus passes, but not hard enough (Haiku also passes)
else:                               R = 1.00   # solvable + Opus passes + Haiku fails — all goals met
```

Map to the two steps:

- **Step 1 ("build")** emits `{0.00, 0.25, 0.50}` and gates with `min_reward = 0.5` (don't
  spend model budget calibrating an unsolvable task).
- **Step 2 ("calibrate")** *re-derives the full ladder* (the author may have broken solvability
  while making the task hard) and emits `{0.50, 0.75, 1.00}`. With `strategy="final"`, the
  trial reward is step 2's — or, if step 1 aborts, step 1's low score. One authoritative
  computation, in step 2.

---

## 5. Directory layout

```
author-a-calibrated-task/
├── task.toml                   # contains the editable [metadata.target] block (§6a)
├── environment/
│   ├── Dockerfile              # author env: harbor + proxy + sandbox SDK; COPYs task.toml + renderer
│   └── render_target.py        # parses [metadata.target] → /app/TARGET.md (and --field lookups)
├── solution/                   # OUTER oracle author (see §12) — makes the meta-task self-checkable
│   └── solve.sh
└── steps/
    ├── build/
    │   ├── instruction.md      # Goal 1: build a valid, solvable inner task in TARGET.md's domain
    │   ├── workdir/
    │   │   └── setup.sh        # render /app/TARGET.md from [metadata.target]; self-delete
    │   └── tests/
    │       └── test.sh         # free checks: build/parse + oracle pass + null fail
    └── calibrate/
        ├── instruction.md      # Goal 2: make Haiku fail without breaking solvability
        ├── workdir/
        │   └── setup.sh        # start metered proxy; reset probe budget; self-delete
        └── tests/
            ├── Dockerfile      # SEPARATE verifier image — grading code the author can't see
            ├── test.sh         # orchestrates oracle + null + 1 Opus + 2 Haiku grade runs
            └── grader.py       # computes the canonical ladder (§4)
```

The inner task the author builds lives at **`/app/inner_task/`** in the shared container
filesystem (persists across steps).

---

## 6. `task.toml`

```toml
schema_version = "1.3"
multi_step_reward_strategy = "final"

[task]
name = "harbor/author-a-calibrated-task"
description = "Agent must author a Harbor task that is solvable, hard for Haiku, and passable by Opus."
keywords = ["meta", "task-authoring", "agent-eval"]

[metadata]
category = "meta"
difficulty_explanation = "Author must calibrate a sub-task into the Haiku-fail / Opus-pass band."

# ════════════════════════════════════════════════════════════════════════════
# ▼▼▼  EDIT HERE — what kind of inner task the author must build  ▼▼▼
# This is the ONE knob you change to retarget the whole meta-task. It is
# rendered into /app/TARGET.md before the author runs (see §6a), so the author
# builds an inner task in THIS domain, graded THIS way, made hard THIS way.
[metadata.target]
# One-line statement of the capability the authored inner task must test.
capability       = "Ability to implement a correct algorithm from a written spec"
# Domain preset. one of: "coding" | "mathematics" | "computer_use" | "data_analysis" | "custom"
domain           = "coding"
# Which Harbor agent the inner Haiku/Opus runs use.
#   coding / math / data → "claude-code";  computer_use → your GUI/computer-use agent id
inner_agent      = "claude-code"
# How the hidden inner verifier decides binary pass/fail.
#   coding → "pytest"            math → "numeric-tolerance"
#   computer_use → "final-state-assertions"   data_analysis → "output-match"
inner_verifier   = "pytest"
# What the author tunes to push Haiku below the fail line (the difficulty lever).
#   coding → "edge cases"        math → "harder instances / required rigor"
#   computer_use → "more steps / stricter UI tolerances"   data → "messier inputs"
difficulty_lever = "edge cases"
# Invariants every authored task must satisfy — these keep the reward honest.
constraints      = "deterministic; binary reward; no network at inner runtime; inner agent sees only instruction.md"
# Degenerate shortcuts to forbid for this domain.
forbidden        = "no hardcoded answers; no reading the hidden tests; no domain mismatch"
# ▲▲▲  END EDIT HERE  ▲▲▲
# ════════════════════════════════════════════════════════════════════════════

[environment]
workdir = "/app"
build_timeout_sec = 1200.0
# Author env may reach ONLY the metered proxy + the sandbox provider. NOT api.anthropic.com.
network_mode = "allowlist"
allowed_hosts = ["app.daytona.io", "*.daytona.io"]   # adjust to your provider; proxy is localhost
cpus = 2
memory_mb = 4096
env = { HARBOR_PROVIDER = "daytona", ANTHROPIC_BASE_URL = "http://localhost:8080" }

# ---- Step 1: build a valid, solvable inner task (free checks only) ----
[[steps]]
name = "build"
min_reward = 0.5                 # must be solvable (reference passes) to proceed

[steps.agent]
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0              # shared env; runs oracle + null (no model tokens)

# ---- Step 2: calibrate difficulty, then grade in an isolated verifier ----
[[steps]]
name = "calibrate"
# Transfer the author's inner task into the separate grading env at its original path.
artifacts = ["/app/inner_task"]  # see §14: confirm directory-artifact support; tar fallback noted

[steps.agent]
timeout_sec = 2400.0
network_mode = "allowlist"
allowed_hosts = ["*.daytona.io"]

[steps.verifier]
environment_mode = "separate"    # grading code lives in the image, hidden from the author
timeout_sec = 3600.0             # must cover 1 Opus + 2 Haiku inner runs

[steps.verifier.environment]
# Built from steps/calibrate/tests/Dockerfile; must ship its own /tests/test.sh.
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com", "*.daytona.io"]
cpus = 2
memory_mb = 4096
# CLEAN Anthropic key the author never sees — grading must be independent of the proxy budget.
env = { ANTHROPIC_API_KEY = "${GRADER_ANTHROPIC_API_KEY}", HARBOR_PROVIDER = "daytona" }
```

---

## 6a. How the target reaches the author (wiring the editable block)

`[metadata.target]` is config, not something the agent sees automatically — instruction.md
does not read `task.toml`. Wire it so the block becomes a file the author reads, single-source:

1. In `environment/Dockerfile`, bake the config and a tiny renderer into the image:
   `COPY task.toml /opt/meta/task.toml` and `COPY render_target.py /opt/render_target.py`.
2. `steps/build/workdir/setup.sh` renders it before the author runs, then self-deletes:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   python3 /opt/render_target.py /opt/meta/task.toml > /app/TARGET.md
   rm -- "$0"
   ```
3. `render_target.py` parses `[metadata.target]` with `tomllib` and writes a short human-readable
   `TARGET.md` (capability, domain, required inner_verifier, difficulty_lever, constraints,
   forbidden). Both step instructions tell the author: **"Read `/app/TARGET.md`; your inner task
   must match it."**

Caveat: because `task.toml` is baked at build time, editing `[metadata.target]` requires a task
rebuild (`--force-build`) to take effect. That's predictable; just remember it when iterating.
The verifier should also read the same block and **reject a domain mismatch** (e.g., the author
built a coding task when `domain = "mathematics"`) so the knob is enforced, not advisory.

---

## 7. Step 1 — "build" (Goal 1)

**`steps/build/instruction.md`** tells the author, in plain terms:

> Read `/app/TARGET.md` first — it specifies the domain, the required verifier style, and the
> constraints your task must satisfy. Create a Harbor task at `/app/inner_task/` that tests the
> capability described there. It must contain `instruction.md`, `environment/Dockerfile`, a
> hidden `tests/` verifier in the style `TARGET.md` requires, and a `solution/` reference that
> passes it. The inner agent will see only your `instruction.md`. Your task must (a) build,
> (b) pass when your reference solution runs, and (c) fail when nothing is done. Do **not**
> attempt to make it hard yet.

**`steps/build/tests/test.sh`** (shared verifier, no model tokens):

```bash
#!/bin/bash
set -uo pipefail
INNER=/app/inner_task
R=0.0

# 1. builds & parses?
if harbor validate -p "$INNER" >/logs/verifier/validate.log 2>&1; then
  # 2. null agent must score 0
  null_r=$(harbor run -p "$INNER" -a null --provider "$HARBOR_PROVIDER" --quiet --print-reward)
  # 3. reference (oracle) must score 1
  ref_r=$(harbor run -p "$INNER" -a oracle --provider "$HARBOR_PROVIDER" --quiet --print-reward)

  if [ "$null_r" = "0.0" ]; then R=0.25; fi
  if [ "$null_r" = "0.0" ] && [ "$ref_r" = "1.0" ]; then R=0.5; fi
fi

echo "{\"reward\": $R, \"null\": ${null_r:-null}, \"ref\": ${ref_r:-null}}" > /logs/verifier/reward.json
```

> `null`, `oracle`, `--print-reward`, and `harbor validate` flag names are placeholders —
> confirm exact agent names / flags in §14. The *logic* is what matters: null must fail,
> oracle must pass, both free.

---

## 8. Step 2 — "calibrate" (Goal 2)

### Author workflow (agent phase)

**`steps/calibrate/instruction.md`** tells the author:

> Make your task hard enough that Haiku 4.5 fails it, **without breaking solvability** — Opus
> 4.8 must still pass from the instruction alone. Strengthen the spec and add edge-case tests
> that a weak model tends to drop, while your reference implementation still passes.
>
> You may probe with the `probe` command, which runs your task against a model in a real
> sandbox and shows you the reward and the inner agent's transcript:
> `probe --model haiku` (≤3 runs) and `probe --model opus` (≤1 run). The budget is enforced;
> calls beyond it are rejected. Probes against the grading models you don't get to see are
> reserved for grading. Edit `/app/inner_task/` and submit when ready.

`probe` is a thin wrapper (§9) that leases a one-time run token from the proxy, then runs
`harbor run -p /app/inner_task -a "$AGENT" -m anthropic/<model>` through it, where `$AGENT` is
`[metadata.target].inner_agent`.

### Grading (separate verifier phase)

**`steps/calibrate/tests/test.sh`** runs in the isolated image with the clean key. It re-runs
the free checks (the author may have regressed solvability while adding difficulty), then
spends the reserved budget:

```bash
#!/bin/bash
set -uo pipefail
INNER=/app/inner_task
P="--provider $HARBOR_PROVIDER --quiet --print-reward"
# Inner agent comes from [metadata.target].inner_agent (claude-code for code/math/data,
# your computer-use agent id for GUI tasks). Renderer also drops it here for the verifier.
AGENT=$(python3 /opt/render_target.py /opt/meta/task.toml --field inner_agent)

null_r=$(harbor run -p "$INNER" -a null   $P)
ref_r=$( harbor run -p "$INNER" -a oracle $P)
opus_r=$(harbor run -p "$INNER" -a "$AGENT" -m anthropic/claude-opus-4-8     $P)
h1=$(    harbor run -p "$INNER" -a "$AGENT" -m anthropic/claude-haiku-4-5-20251001 $P)
h2=$(    harbor run -p "$INNER" -a "$AGENT" -m anthropic/claude-haiku-4-5-20251001 $P)

python3 /tests/grader.py \
  --build_ok 1 --null "$null_r" --ref "$ref_r" \
  --opus "$opus_r" --haiku "$h1" --haiku "$h2" \
  > /logs/verifier/reward.json
```

**`steps/calibrate/tests/grader.py`** implements §4 verbatim and emits
`{"reward": R, "null": ..., "ref": ..., "opus": ..., "haiku": [h1, h2]}`. Treat a missing/None
inner reward as failure (0.0) for that agent. `build_ok` is 1 here because step 1's gate
already required a buildable, solvable task; if you want belt-and-suspenders, re-run
`harbor validate` first and set `build_ok` accordingly.

---

## 9. The metered proxy (budget enforcement) — your FastAPI/audit-log wheelhouse

The author env's only route to the Anthropic API is a local proxy (`ANTHROPIC_BASE_URL=
http://localhost:8080`); the network allowlist blocks `api.anthropic.com` directly. The proxy
meters **runs**, not API calls (one inner `harbor run` makes many calls):

- `POST /lease {model}` → if that model's run budget > 0, decrement it, return a one-time
  `token`; else 429. `probe` calls this once per run and injects the token into the inner run's
  requests (header or per-run key).
- All forwarded `/v1/messages` calls must carry a valid, unexhausted token, else 403. This is
  why the author physically cannot exceed 3 Haiku / 1 Opus regardless of how they invoke
  harbor.
- Append every lease + call to an audit log (SQLite or Postgres — same shape as your
  Gmail/Calendar middleware project). The verifier reads it only for bookkeeping/anomaly flags,
  not as the primary gate; the lease counter is the real gate.

`steps/calibrate/workdir/setup.sh` starts the proxy, resets the budget to `{opus:1, haiku:3}`,
waits for `/health`, then `rm -- "$0"` so the author can't read it. Keep grading entirely off
this proxy — the separate verifier env uses the clean key, so its 1 Opus + 2 Haiku are
independent of and invisible to the author.

---

## 10. Inner-task contract (parameterized by `[metadata.target]`)

Whatever the domain, the author must produce at `/app/inner_task/`:

- `instruction.md` — the problem statement the inner agent sees. Hidden tests must not be
  derivable verbatim from it, but it must be *fairly* solvable (Opus has to pass).
- `environment/` — a minimal image suited to the domain.
- `tests/` — a hidden verifier in the style `inner_verifier` requires, writing `reward.txt`
  (1 on full pass, else 0). Harbor copies `tests/` in at verify time, so the **inner agents
  never see it** — anti-overfit is structural for every domain.
- `solution/` — the reference that passes the hidden verifier.

Keep the inner reward **binary** in every domain — it keeps the §4 ladder unambiguous. "Binary"
just means "fully correct vs not": all pytest cases pass, the numeric answer is within
tolerance, the final UI/file state matches, etc.

How the four target fields specialize per domain (coding is the worked default; the rest are
the patterns to follow when you flip the knob):

| `domain` | `inner_agent` | `inner_verifier` | `difficulty_lever` | "fully correct" means |
|---|---|---|---|---|
| `coding` (default) | `claude-code` | `pytest` over a hidden suite | edge cases the weak model drops | all tests green |
| `mathematics` | `claude-code` | numeric/symbolic check with tolerance (e.g. `sympy`) | harder instances; required derivation steps; tighter tolerance | answer matches within tolerance |
| `computer_use` | your GUI/computer-use agent | assertions on final app/file/DOM state | more steps; stricter UI tolerances; fewer affordances | end state matches the target |
| `data_analysis` | `claude-code` | exact/approx match of an output artifact (CSV/JSON) | messier inputs; trickier joins/edge rows | output equals reference |
| `custom` | as you set | as you set | as you set | as your verifier defines |

Goal 2 ("make Haiku fail without breaking solvability") is the same move in every domain:
strengthen along `difficulty_lever` until Haiku drops below the line while the reference still
passes. Only the lever's flavor changes. The verifier must also confirm the authored task's
domain matches `[metadata.target].domain` (per §6a) so a flipped knob is actually enforced.

---

## 11. Plumbing & networking (the main implementation risk)

This is Harbor running Harbor. Do **not** use Docker-in-Docker. Configure inner `harbor run`
to launch on a **remote sandbox provider** (Daytona or Modal) from both the author env (probes)
and the verifier env (grades). Decisions Claude Code needs to make early:

- Provider + credentials available in both the author env and the separate verifier env.
- Author env allowlist = proxy (localhost) + provider hosts only.
- Verifier env allowlist = `api.anthropic.com` + provider hosts; clean key via
  `GRADER_ANTHROPIC_API_KEY`.
- Confirm the provider supports the concurrency you need (you fire up to 3 inner runs back to
  back at grade time).

---

## 12. Oracle author solution (makes the meta-task self-checkable)

`solution/solve.sh` is a *reference author*: a script that writes a known-good `/app/inner_task/`
(an inner task **matching the configured `[metadata.target]` domain**, with a pre-calibrated
difficulty lever known to be Opus-pass / Haiku-fail) and performs the trivial step-2 edits.
Keep one reference inner task per domain you actually use so the oracle check stays valid when
you flip the knob. Running the OUTER task with `-a oracle` should yield reward **1.0**. This is
your end-to-end smoke test — if the oracle author doesn't score 1.0, the harness is wrong, not
the agent. Build a deliberately-too-easy variant too, to confirm it caps at 0.75 (Haiku also
passes), and an unsolvable variant to confirm it caps at 0.50.

---

## 13. Build order (milestones — stop after each for an oracle check)

1. `harbor init --task harbor/author-a-calibrated-task`; lay down §5 skeleton + §6 `task.toml`.
2. Set `[metadata.target]` (§6a) + write `render_target.py` and both `workdir/setup.sh`
   renders; confirm `/app/TARGET.md` appears in the author env and `--field inner_agent` works.
3. Inner-task contract (§10) + a hand-written known-good inner task **in the target domain**.
4. Step-1 verifier (§7); confirm null=0 / oracle=1 on the known-good inner task.
5. Metered proxy + `probe` wrapper (§9); confirm budget caps and 429/403 behavior.
6. Separate grading env + `grader.py` (§8); confirm the §4 ladder on hand-built
   pass/cap/too-easy inner tasks; confirm the domain-mismatch rejection.
7. Oracle author `solution/solve.sh` (§12); run OUTER with `-a oracle`, expect 1.0.
8. Dry-run with a real author agent end to end; check the audit log shows ≤3 Haiku + ≤1 Opus
   probes and grading used exactly 1 Opus + 2 Haiku.

---

## 14. Confirm against your installed Harbor version (honest unknowns)

- Exact agent identifiers for **null** and **oracle**, and whether a `--print-reward` / quiet
  flag exists (else read `/logs/verifier/reward.json` from the inner run dir).
- `harbor validate` (or equivalent) for the build/parse check.
- Whether `artifacts = ["/app/inner_task"]` copies a **directory** to the separate verifier
  env. If only files transfer, have step 1 emit a tarball (`/app/inner_task.tar`) and declare
  that instead; untar in the grading `test.sh`.
- How to pin the inner run's provider + credentials from inside a sandboxed container on your
  provider.
- Per-run token injection mechanism for the proxy (custom header vs. per-run key) given how
  `claude-code` reads `ANTHROPIC_BASE_URL`.
- Whether you prefer baking `task.toml` into the image for `render_target.py` (rebuild on every
  `[metadata.target]` edit) or staging the block as a `workdir/` file (no rebuild, but a second
  copy to keep in sync). Baked is the §6a default; pick one and be consistent.

---

## 15. Known limitations (by design, not bugs)

- **One Opus grade = one sample.** Solvability is existential, so a single clean pass is valid
  proof a path exists; but a task Opus passes ~90% of the time still false-negatives ~10% of
  runs from pure variance, with no author recourse. Upside: it pressures authors toward
  *robustly* solvable tasks. Fix when budget allows: a second Opus grade with "≥1 of 2".
- **Two Haiku grades estimate "too hard" from two samples** — a threshold, not a pass-rate.
  Coarse but budget-bound.
- **Quirk vs. capability.** Opus-pass / Haiku-fail is honest *discrimination* but doesn't prove
  the difficulty is about capability X rather than a Haiku-specific quirk. A later hardening:
  require the Haiku failures to land on the X-relevant test cases.
- **Reference-as-pre-filter only.** The reference no longer proves solvability (Opus does); it's
  a free gate to avoid spending tokens on broken tasks.
