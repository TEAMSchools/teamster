# Hooks

Two hooks guard secrets and sensitive paths:

- **`check-sensitive.sh`** — PreToolUse: blocks tool calls that touch sensitive
  paths or write sensitive content
- **`check-output.sh`** — PostToolUse: blocks tool results containing secret
  material (keys, tokens, connection strings)

See each script for exact regex patterns. This document covers operational
behavior.

## What is blocked

**Secret paths** (all tools blocked) — dotenv files, private key/cert files, SSH
directory, secret-volume, credentials JSON files, devcontainer template
directory. See rule 1 and 1b in `check-sensitive.sh` for the full pattern list.

**Read-only paths** (Edit/Write/Bash blocked; Read/Grep/Glob allowed):

- `check-sensitive.sh` and `check-output.sh` themselves
- `.claude/settings.json`, `.claude/shell-snapshots/`
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
(PostToolUse).

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
