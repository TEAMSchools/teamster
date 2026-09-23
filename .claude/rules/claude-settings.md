---
paths:
  - ".claude/settings.json"
  - ".claude/settings.local.json"
  - ".claude/hooks/**"
  - ".devcontainer/scripts/**"
  - ".claude/context/**"
---

# Editing hooks and settings

Loads on the first read of a hook script, a settings file, a devcontainer
script, or a `.claude/context/` file. Hook block list: `.claude/CLAUDE.md`.

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

## Hook protocol

Claude Code hooks communicate decisions via **stdout JSON + exit code 0**:

- **Allow**: exit 0 with no output (or empty stdout)
- **PreToolUse deny**: exit 0 with
  `{"hookSpecificOutput": {"permissionDecision": "deny", ...}}` on stdout
- **PostToolUse redact**: exit 0 with
  `{"hookSpecificOutput": {"updatedToolOutput": <redacted tool_response>, ...}}`.
  PostToolUse cannot deny: the tool already ran, and `permissionDecision` is
  silently ignored on this event (the scanner emitted it for months with no
  effect). `updatedToolOutput` must keep the tool's output shape or the harness
  drops it and shows the original. `{"decision": "block", "reason": ...}` ends
  the turn with a warning and is used only when there is nothing to redact.

**Exit 1 is a non-blocking error** — Claude Code logs it but executes the tool
anyway. Never use `exit 1` to deny. Never write deny JSON to stderr (`>&2`). The
regression test suite (`expect_deny_exit0`) enforces both invariants.

Auto mode does not replace either hook: `permissions.deny` and PreToolUse hooks
run before the classifier, and the classifier never sees tool results.

## Context injection (`tool-gotchas.sh`)

A third hook adds context instead of blocking. `tool-gotchas.sh` (PreToolUse,
matcher `Agent|Workflow|mcp__.*`) injects `.claude/context/<key>.md` the first
time a key is used in a session. The key is the server segment of an MCP tool
name (`mcp__<server>__<tool>`), or `agent` for the `Agent` and `Workflow` tools.
Add or change guidance for a server by editing that file — no hook or settings
change needed. A new non-MCP tool needs a new `case` arm in the script.

- It fails **open** (unparseable payload → exit 0, call proceeds) because it
  only adds context. The two guard hooks fail closed — do not copy this pattern
  into them.
- `additionalContext` is consumed by PreToolUse at runtime but is NOT in the
  harness's documented PreToolUse schema (only `permissionDecision`,
  `permissionDecisionReason`, `updatedInput` are). If injection silently stops
  after an upgrade, move the matcher to PostToolUse, where the field IS
  documented; the script echoes the event name back, so it needs no edit.
- Fires once per session per server, tracked by
  `.claude/scratch/.gotchas-<session>-<server>`. A SessionStart `compact` hook
  deletes those markers so the guidance survives a compaction.
