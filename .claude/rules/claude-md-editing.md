---
paths:
  - "**/CLAUDE.md"
  - "CLAUDE.local.md"
  - ".claude/rules/**"
  - ".claude/context/**"
  - ".claude/skills/**"
---

# Editing CLAUDE.md, context, rules, and skill files

Loads on the first read of a CLAUDE.md, a rule, a context file, or a skill.

- Before adding a line to any of these files: name the specific decision Claude
  will make differently because of it. If you cannot, cut it.
- When a change deletes something, delete the text about it; do not add text
  saying it was deleted. A tombstone ("`X` was retired", "there is no longer a
  `Y`") reads like it passes the necessity test and does not — the decision it
  guards against cannot arise once nothing surfaces the name. Add the negative
  only when a live pointer survives, and then point at the replacement, not at
  the corpse. Retirement history belongs in the commit message and the diff.
- Where a new line goes: one MCP server's behavior goes in
  `.claude/context/<server>.md` (auto-injected on first use). One directory's
  specifics go in that directory's CLAUDE.md. Worktree mechanics go in
  `.claude/rules/worktrees.md`. Subagent dispatch goes in
  `.claude/context/agent.md`. Conventions scoped by file type or spanning
  directories go in `.claude/rules/<topic>.md` with `paths:` (dbt SQL, dbt YAML,
  Cube models, hooks and settings). Runbooks with no file trigger go in a skill.
  The root CLAUDE.md keeps only what must be known BEFORE any tool runs: safety
  prohibitions, branch and PR etiquette, and rules whose violation produces a
  silently wrong answer rather than a loud error.
- A new `.claude/rules/<topic>.md` whose `paths:` reach outside `src/dbt/` and
  `src/cube/` needs the first _Tooling_ bullet widened to match. That bullet
  names the trees to open with Read instead of `cat`; a rule outside them loads
  for nobody who reads the file through Bash.
- Bold is reserved for the root _Never_ block. Elsewhere, bold only a line a
  reader who skims must not miss.
