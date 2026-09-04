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
  message (false positive on keywords), fall back to writing the message to
  `.claude/scratch/commit-msg.txt` using the Write tool, then
  `git commit -F .claude/scratch/commit-msg.txt`. The Write tool's `content`
  field is exempt from path/keyword scanning. The Bash tool `description` field
  is also scanned — keep it generic (e.g. "Commit changes"). Delete any stale
  file first (`rm -f .claude/scratch/commit-msg.txt`) — if it exists from a
  prior session, Write fails ("File has not been read yet") but a batched
  `git commit -F` still runs and consumes the old content, producing a commit
  with the wrong message.

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
