"""Programmatic structural guardrails for the Harbor-task tutor skill.

These are cheap, deterministic checks: the file must exist at the agreed output
path, look like a real Claude skill (YAML frontmatter), mention every core
Harbor task-building concept the instruction requires, and not be a stub.

They deliberately do NOT judge quality or pedagogy — a keyword-stuffed file
could pass all of these. Quality (genuine interactivity, accuracy of Harbor
details, completeness, beginner-friendliness) is graded by the LLM judge in
judge.toml. The two are blended into the final reward.

Built-in criteria are called via the rewardkit.criteria module; each call
registers a check in the current discovery session. Paths are relative to the
workspace (/app), where the agent wrote skill.md.
"""

from pathlib import Path

from rewardkit import criteria, criterion

SKILL = "skill.md"

# 1. The skill exists at the agreed output path (/app/skill.md).
criteria.file_exists(SKILL)

# 2. It's a real Claude skill: YAML frontmatter with name + description at the
#    very top, closed by a '---' line.
criteria.file_contains_regex(SKILL, r"(?s)\A\s*---.*?\bname:.*?\bdescription:.*?\n---")

# 3. Mentions each core Harbor artifact / command the tutorial must cover.
criteria.file_contains_regex(SKILL, r"harbor task init")
criteria.file_contains_regex(SKILL, r"task\.toml")
criteria.file_contains_regex(SKILL, r"Dockerfile")
criteria.file_contains_regex(SKILL, r"test\.sh")
criteria.file_contains_regex(SKILL, r"solve\.sh|solution/")
criteria.file_contains_regex(SKILL, r"harbor run")            # run the verifier
criteria.file_contains_regex(SKILL, r"reward\.(txt|json)")    # reward mechanism

@criterion(description="skill.md is substantial (>= 300 words), not a stub")
def skill_is_substantial(workspace: Path) -> bool:
    p = workspace / SKILL
    if not p.exists():
        return False
    return len(p.read_text().split()) >= 300
