---
paths:
  - ".claude/settings.json"
  - ".claude/settings.local.json"
  - ".claude/hooks/**"
  - ".devcontainer/scripts/**"
---

# Editing hooks and settings

Loads on the first read of a hook script, a settings file, or a devcontainer
script. Hook block list and protocol: `.claude/CLAUDE.md`.

## Modifying protected files

- Hook scripts (`.claude/hooks/**/*.sh`), `.devcontainer/scripts/`, and
  `.claude/settings.json` / `.claude/settings.local.json`: draft changes,
  present to user for manual application using complete code blocks — show only
  the final replacement block, never an old+new pair (which reads like a diff
  and invites copy errors) — with a file + line number link, ordered
  top-to-bottom, commentary separate from the edits
- Those files must also be staged and committed manually
- Other `.claude/` files (e.g. `CLAUDE.md` files) may be edited directly
- When staging changes that include protected paths, use `git add -u` — naming
  them explicitly in `git add <file>` triggers the hook and gets blocked
- **Git commit messages**: Try `git commit -m` first. If the hook blocks the
  message (false positive on keywords), fall back to writing the message with
  the Write tool — whose `content` field is exempt from path/keyword scanning —
  then `git commit -F <path>`. The Bash tool `description` field is also
  scanned, so keep it generic (e.g. "Commit changes").

  Write it to your SESSION scratchpad (absolute path in the system prompt), one
  file per commit: `<scratchpad>/commit-msg-<slug>.txt`. No hook rule covers
  that path, and it is isolated per session. Do NOT use a shared fixed path such
  as `.claude/scratch/commit-msg.txt`: that directory is per-checkout, so two
  sessions in one worktree race on the same file. The old remedy — `rm -f` the
  stale file — deletes a concurrent session's pending message, and leaving it in
  place is worse: Write fails ("File has not been read yet") while a batched
  `git commit -F` still runs and consumes the other session's content, producing
  a commit with someone else's message.

## permissions.deny vs hooks

`Bash(<pattern>)` deny rules match from the **start** of the command only. Hooks
scan the full command string. For `op`, both are needed — do not remove one in
favor of the other.

## permissions.deny path prefixes

Rules for project-root paths use `/` (e.g. `Edit(/.claude/hooks/**/*.sh)`).
Rules for home-dir paths must use `~` (e.g.
`Edit(~/.claude/shell-snapshots/**)`). Using `/` for a home-dir path silently
fails — the rule never matches.

Glob depth: `Edit(/.claude/skills/**)` may not match deeply nested paths. When
an approval prompt appears despite an apparently-covering rule, accept it — the
dialog auto-adds a narrower per-subdirectory rule that works.

## Settings file integrity

Hooks and `permissions.deny` rules are defined in `.claude/settings.json`
(JSONC). If the parser rejects the file, **all settings are silently ignored** —
no hooks fire, no deny rules apply. Claude Code does not log a warning.

- Keep `settings.json` as clean JSONC — avoid large commented-out blocks
- Validate after edits: the file must parse as valid JSONC
- Symptoms of a broken file: hooks stop firing, deny rules stop blocking, no
  error messages
- Recovery: validate by running `bash tests/hooks/run_all.sh` (denials should
  pass); if hooks still don't fire, restore `.claude/settings.json` from git.
  Hooks resume on the next tool call after fix.

## Regression tests and hook editing

See `.claude/hooks/CLAUDE.md` (loads when working under `.claude/hooks/`):
`bash tests/hooks/run_all.sh`, ad-hoc rule probing via a scratch harness, and
the recurring gotchas when editing the hooks (phantom CI revert, `SC2312`).
