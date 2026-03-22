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

**Read-only paths** (Edit/Write/Bash blocked; Read/Grep/Glob allowed):

- `check-sensitive.sh` and `check-output.sh` themselves
- `.claude/settings.json`, `.claude/settings.local.json`,
  `.claude/shell-snapshots/`
- `.devcontainer/scripts/`
- `.git/hooks/`
- `.trunk/trunk.yaml`, `.trunk/config/`

Note: `*.md` files under `.claude/hooks/` (like this CLAUDE.md) are writable.

**Bash-only rules** (do NOT fire for Read, Write, Edit, Grep, or Glob):

- Environment variable / process memory leakage (`printenv`, `set`, `env`, etc.)
- 1Password CLI commands (`op vault`, `op item`, etc.)
- Encoding bypass attempts (base64-to-shell pipes, Python exec/eval obfuscation)
- Shell variable expansion (`$UPPER_CASE` vars not on the safe list)

**BigQuery MCP** — queries must start with SELECT/SHOW/DESCRIBE/WITH; embedded
DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) is blocked.

**Output scanning** (PostToolUse) — blocks tool results containing secret
material (keys, tokens, connection strings, high-entropy strings). Fires for
Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch, and MCP tools. Does NOT
fire for Edit.

## Modifying protected files

- Hook scripts and `.devcontainer/scripts/`: draft changes, present to user for
  manual application
- Files under `.claude/` must be staged and committed manually

## Regression tests

```bash
bash tests/hooks/run_all.sh
```

Individual suites are in `tests/hooks/test_*.sh`. Test files contain sensitive
fixture strings (gitleaks ignores are required). The `expect_deny_exit0` helper
in `helpers.sh` guards against the exit-code and stderr regressions described
above.
