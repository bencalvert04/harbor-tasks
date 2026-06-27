Note from Ben: this is the simplest task but uses reward kit to offer partial rewards and LLMaaJ to decide the effectiveness of the skill

# Harbor/skill-builder

The agent is asked to **write a Claude skill** — a system-prompt markdown file with
YAML frontmatter — that acts as an interactive tutor walking a beginner step-by-step
through building their first Harbor task. The full prompt is in
[`instruction.md`](instruction.md). The agent must research the real Harbor layout /
`task.toml` schema / verifier model, then write the skill to `/app/skill.md`, one file
at a time rather than dumping everything at once.

## Environment

- Base image: `ubuntu:24.04` (see `environment/Dockerfile`).
- Installed: `ca-certificates`, `curl`, `git` — so the agent can use the granted
  internet access (`allow_internet = true`) to look up the Harbor docs/repo.
- Resources: 1 CPU, 2 GB RAM, 10 GB disk, no GPU.
- Agent timeout: 600 s.

## Verifier

Reward Kit (`tests/test.sh` → `uvx --from 'harbor-rewardkit==0.1.*' rewardkit /tests`)
runs in the **shared** agent environment over a flat `tests/` layout. Two rewards are
discovered and blended 50/50 into a single `reward` score:

| Source | Dimension | Type | Measures |
| --- | --- | --- | --- |
| `checks.py` | structural guardrails | programmatic | `skill.md` exists, has YAML frontmatter (`name`/`description`), mentions each core concept (`harbor task init`, `task.toml`, `Dockerfile`, `test.sh`, `solve.sh`/`solution/`, `harbor run`, `reward.txt`/`reward.json`), and is ≥ 300 words. Mean of all checks. |
| `judge.toml` | `interactive_tutoring` (×2) | LLM judge | Genuinely interactive, one-file-at-a-time tutoring vs. a wall of text |
| `judge.toml` | `harbor_accuracy` (×2) | LLM judge | Commands, folder layout, `task.toml` schema, and reward mechanism are correct, not fabricated |
| `judge.toml` | `completeness` (×1) | LLM judge | Covers the full workflow: scaffold → instruction → env → verifier → solution → config → verify |
| `judge.toml` | `beginner_friendly` (×1) | LLM judge | Clear, explains *why*, no unexplained jargon |

Aggregation: each reward is a weighted mean of its criteria (Likert scores normalized to
0–1); the programmatic reward and the judge reward are then averaged (`reward_weight`
1.0 each) into the final `reward`. Tune the balance via `[judge].weight` in
`judge.toml`.

The judge calls `anthropic/claude-sonnet-4-6` via litellm, so the verifier needs
`ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`) — wired through `[verifier.env]` in
`task.toml`, pulled from the host env at run time.

> **Note on grading prose:** because half the reward is an LLM judge, the Oracle will
> score *high but not necessarily exactly 1.0* — judges rarely return a perfect 5/5 on
> every Likert dimension. The signal that matters is **good ≫ bad**, not a hard 1.0.

## Layout

```
skill-builder/
├── instruction.md          # Prompt: write the tutor skill to /app/skill.md
├── task.toml               # Config; [verifier.env] passes ANTHROPIC_API_KEY
├── environment/Dockerfile  # ubuntu:24.04 + curl/git/ca-certificates
├── solution/solve.sh       # Oracle: writes the canonical create-task skill to /app/skill.md
├── tests/
│   ├── test.sh             # Verifier entrypoint → rewardkit /tests
│   ├── checks.py           # Programmatic structural guardrails
│   └── judge.toml          # LLM-judge rubric (4 quality dimensions)
└── README.md
```

## Running

```bash
# Sanity-check against the reference solution (expect a high, near-1.0 score):
ANTHROPIC_API_KEY=sk-ant-... harbor run -p skill-builder -a oracle

# Test a real agent:
ANTHROPIC_API_KEY=sk-ant-... harbor run -p skill-builder -a terminus-2 -m anthropic/claude-sonnet-4-6
```
