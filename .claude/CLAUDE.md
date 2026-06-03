# Hooks

If a tool call is denied, returns empty unexpectedly, or `git add` blocks,
suspect a hook first. This file documents what the two hooks block and the
approved bypasses.

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

**WebFetch / MCP input scanning** — PreToolUse scans URLs and query strings for
sensitive keywords (e.g., `/auth` in URL paths, `JWT` / `secret` / `credential`
/ `signing key` in context7 query strings). Symptom: "Cannot access sensitive
path" with no further detail. Rephrase the URL or query (generic terms like
"user context", "header format") to get past it.

**Secret paths** (all tools blocked) — dotenv files, private key/cert files, SSH
directory, secret-volume, credentials JSON files, devcontainer template
directory. See `check-sensitive.sh` for the full pattern list.

**Silent hook blocks on search**: Grep/Glob on `.devcontainer/tpl/` for patterns
containing sensitive keywords returns "No files found" — not a clear denial. Do
not trust empty results in that directory.

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
- 1Password CLI commands (`op vault`, `op item`, `op read`, `op run`,
  `op document`, `op inject`, etc.)
- Encoding bypass attempts (base64-to-shell pipes, Python exec/eval obfuscation)
- Shell variable expansion (`$UPPER_CASE` vars not on the safe list)

**MCP arg hygiene:** Never write the bare token `env` (with surrounding
whitespace) in any string passed to `mcp__*` tools — comment bodies, PR
descriptions, commit messages, issue bodies. Spell it `environment variable`.
The PreToolUse hook's path regex matches `env` and denies the call. (Exception:
for dbt Cloud `trigger_job_run` specifically, fall back to
`git commit --allow-empty && git push` — the GitHub webhook fires CI with the
correct schema override.)

**Writing about the hooks self-blocks:** an issue/PR/commit/comment body
containing the tokens the hooks deny gets your own `mcp__*`/Bash write denied.
Beyond bare `env`: `.env`/`.environment` (Rule 1 `\.env[.a-z]*` is unanchored —
matches anywhere, even mid-word in prose), bounded dotfile/cert paths,
`/proc/*/environ`, and secret-shaped fixtures (`op://`, key headers — these also
trip `check-output.sh` on the _response_). Reword/backtick them, or keep literal
evidence in `.claude/scratch/` and reference it. For non-Bash tools only Section
1 path rules scan the body; Bash-only and `path_only` rules do not. (Edit/Write
`content`/`new_string` is content-exempt, so editing docs is unaffected.)

**BigQuery MCP** — queries must start with SELECT/SHOW/DESCRIBE/WITH; embedded
DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) is blocked.

**Output scanning** (PostToolUse) — blocks tool results containing secret
material (keys, tokens, connection strings, high-entropy strings). Fires for
Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch, and MCP tools. Does NOT
fire for Edit.

## Git authentication for new repos

The Codespace `GITHUB_TOKEN` (`ghu_*`) only has access to the repo it was
provisioned for. Pushing to other org repos requires bypassing it:
`GITHUB_TOKEN= git -c credential.helper='!gh auth git-credential' push`

The Codespace token also lacks `project` and org-admin scopes. `gh` calls that
mutate ProjectV2 items/fields fail with "Resource not accessible by integration"
— prefix with `GITHUB_TOKEN=` to fall back to the user's OAuth token (`gho_*`)
which has full scopes.

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

## Scratch directory

`.claude/scratch/` is gitignored and writable by all tools. Use it for temp
files (commit messages, draft content) that would otherwise be blocked by hooks.

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

## Regression tests

```bash
bash tests/hooks/run_all.sh
```

Individual suites are in `tests/hooks/test_*.sh`. Test files contain sensitive
fixture strings (gitleaks ignores are required). The `expect_deny_exit0` helper
in `helpers.sh` guards against the exit-code and stderr regressions described
above.

**Ad-hoc rule probing:** a Bash command that names `.claude/hooks/*.sh` is
blocked (Rule 2), and trigger tokens placed in the command self-block. To test a
rule, `Write` a harness into `.claude/scratch/` (Write `content` is exempt from
scanning) that pipes fixtures into the hook by absolute path, then run
`bash .claude/scratch/<name>.sh` (the command string carries no triggers).
