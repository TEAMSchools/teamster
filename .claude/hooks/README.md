# Hooks

Two hooks guard secrets and sensitive paths:

- **`check-sensitive.sh`** — PreToolUse: blocks tool calls that touch sensitive
  paths or write sensitive content
- **`check-output.sh`** — PostToolUse: blocks tool results containing secret
  material (keys, tokens, connection strings)

See each script for exact regex patterns. This document covers operational
behavior.

## check-sensitive.sh structure

The hook is organized into three sections by tool type:

**Section 1 — All tools (path-based protection):**

- Rule 1/1b: Sensitive file/directory patterns (dotenv, keys, certs,
  secret-volume, devcontainer templates)
- Rule 1c: High-risk proc/dev paths (`/proc/*/environ`, `/proc/*/cmdline`,
  `/dev/fd/`) — kept in all-tools scope because the VSCode extension doesn't
  support sandbox and MCP tool inputs bypass it
- Rule 2: Hook self-protection (block writes to hook scripts, settings,
  devcontainer scripts, git hooks, trunk config)

**Section 2 — Bash only (command-pattern protection):**

- Rule 3/3b/3c: Environment variable / process memory leakage
- Rule 4: 1Password CLI commands
- Rule 5/5a-5d: Encoding bypass attempts
- Rule 7: Shell variable expansion (`$VAR`)

These rules do NOT fire for Read, Write, Edit, Grep, or Glob — only for Bash
commands.

**Section 3 — BigQuery MCP (read-only enforcement):**

- Rule 8: Blocks DML/DDL in BigQuery MCP queries

## What is blocked

**Secret paths** (all tools blocked) — dotenv files, private key/cert files, SSH
directory, secret-volume, credentials JSON files, devcontainer template
directory. See Rule 1 and 1b in `check-sensitive.sh` for the full pattern list.

**Read-only paths** (Edit/Write/Bash blocked; Read/Grep/Glob allowed):

- `check-sensitive.sh` and `check-output.sh` themselves
- `.claude/settings.json`, `.claude/settings.local.json`,
  `.claude/shell-snapshots/`
- `.devcontainer/scripts/`
- `.git/hooks/`
- `.trunk/trunk.yaml`, `.trunk/config/`

Note: `*.md` files under `.claude/hooks/` (like this one) are writable.

**Content scanning** (applies to Edit `new_string` and Write `content`):

- Uppercase shell variable assignments (`export VAR=value`) trigger the env-var
  scanner — use lowercase locals as a workaround
- Test files with sensitive fixture strings must be drafted for manual
  application
- Files whose content references the exact blocked patterns (like this README)
  are themselves subject to content scanning — write around triggering strings
  where needed

**Output scanning**: tool results containing secret material are denied
(PostToolUse). The output scanner does NOT fire for Edit tool calls — only for
Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch, and MCP tools.

## Modifying protected files

- Hook scripts and `.devcontainer/scripts/`: draft changes, present to user for
  manual application
- Files under `.claude/` must be staged and committed manually

## Regression tests

```bash
bash tests/hooks/run_all.sh
```

Individual suites are in `tests/hooks/test_*.sh`. Test files contain sensitive
fixture strings — edits must be drafted for manual application.
