# Hooks

Two hooks guard secrets and sensitive paths:

- **`check-sensitive.sh`** — PreToolUse: blocks tool calls that touch sensitive
  paths or write sensitive content
- **`check-output.sh`** — PostToolUse: blocks tool results containing secret
  material (keys, tokens, connection strings)

See each script for exact regex patterns. This document covers operational
behavior.

## Hook protocol

Claude Code hooks communicate decisions via **stdout JSON + exit code 0**:

- **Allow**: exit 0 with no output (or empty stdout)
- **Deny**: exit 0 with
  `{"hookSpecificOutput": {"permissionDecision": "deny", ...}}` on stdout

**Exit 1 is a non-blocking error** — Claude Code logs it but executes the tool
anyway. Never use `exit 1` to deny. Never write deny JSON to stderr (`>&2`). The
regression test suite (`expect_deny_exit0`) enforces both invariants.

## What is blocked

**Secret paths** (all tools blocked) — dotenv files, private key/cert files, SSH
directory, secret-volume, credentials JSON files, devcontainer template
directory. See `check-sensitive.sh` for the full pattern list.

**High-risk proc/dev paths** (all tools blocked) — `/proc/*/environ`,
`/proc/*/cmdline`, `/dev/fd/`.

**Read-only paths** — Edit/Write blocked by `permissions.deny` in
`settings.json`; Bash blocked entirely by hook Rule 2 — Bash commands (even
read-only ones) can pipe or chain output past `check-output.sh`, whereas
Read/Grep/Glob always run through it. Read/Grep/Glob allowed:

- `check-sensitive.sh` and `check-output.sh` themselves
- `.claude/settings.json`, `.claude/settings.local.json`,
  `.claude/shell-snapshots/`
- `.devcontainer/scripts/`
- `.git/hooks/`
- `.trunk/trunk.yaml`, `.trunk/config/`

Note: `*.md` files under `.claude/` (like this CLAUDE.md) are writable.

**Claude CLI via Bash** — the `claude` binary lives under
`~/.vscode-remote/extensions/` and is not on `$PATH`, so it cannot be run via
Bash. Plugin and marketplace commands (`claude plugins install`,
`claude plugins marketplace list`, etc.) must be run manually in a terminal.

**Bash-only rules** (do NOT fire for Read, Write, Edit, Grep, or Glob):

- Environment variable / process memory leakage (`printenv`, `set`, `env`, etc.)
- 1Password CLI commands (`op vault`, `op item`, `op read`, `op document`,
  `op inject`, etc.)
- Encoding bypass attempts (base64-to-shell pipes, Python exec/eval obfuscation)
- Shell variable expansion (`$UPPER_CASE` vars not on the safe list)

**BigQuery MCP** — queries must start with SELECT/SHOW/DESCRIBE/WITH; embedded
DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) is blocked.

**Output scanning** (PostToolUse) — blocks tool results containing secret
material (keys, tokens, connection strings, high-entropy strings). Fires for
Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch, and MCP tools. Does NOT
fire for Edit.

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
- **Git commit messages**: Write the message to `/tmp/commit-msg.txt` using the
  Write tool, then `git commit -F /tmp/commit-msg.txt`. The Write tool's
  `content` field is exempt from path/keyword scanning, so the message body
  never triggers false positives. The Bash tool `description` field is also
  scanned — keep it generic (e.g. "Commit changes").

## permissions.deny path prefixes

Rules for project-root paths use `/` (e.g. `Edit(/.claude/hooks/**/*.sh)`).
Rules for home-dir paths must use `~` (e.g.
`Edit(~/.claude/shell-snapshots/**)`). Using `/` for a home-dir path silently
fails — the rule never matches.

## Settings file integrity

Hooks and `permissions.deny` rules are defined in `.claude/settings.json`
(JSONC). If the parser rejects the file, **all settings are silently ignored** —
no hooks fire, no deny rules apply. Claude Code does not log a warning.

- Keep `settings.json` as clean JSONC — avoid large commented-out blocks
- Validate after edits: the file must parse as valid JSONC
- Symptoms of a broken file: hooks stop firing, deny rules stop blocking, no
  error messages

## Regression tests

```bash
bash tests/hooks/run_all.sh
```

Individual suites are in `tests/hooks/test_*.sh`. Test files contain sensitive
fixture strings (gitleaks ignores are required). The `expect_deny_exit0` helper
in `helpers.sh` guards against the exit-code and stderr regressions described
above.
