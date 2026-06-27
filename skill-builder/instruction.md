Write a Claude skill (system prompt markdown file) that acts as an interactive tutor to guide a beginner step-by-step through building their first Harbor task.

Write your finished skill to `/app/skill.md`. It must be a valid Claude skill: YAML frontmatter (with `name` and `description`) followed by the markdown instructions the agent will follow.

Before writing the skill:
1. Search the web or consult the official Harbor repository/docs to look up the exact folder structure, `task.toml` schema (v1.2), and verifier/reward specifications.
2. Ensure the generated skill instructs the agent to walk the user through one file at a time (task.toml, Dockerfile, test scripts, solution, and running the local verifier command) rather than dumping all the files at once.
