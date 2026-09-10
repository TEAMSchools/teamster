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

## What is blocked

**Outbound secret-value egress scan** (PreToolUse, Section 4) — write-capable
MCP tools (tool name contains
`create`/`update`/`write`/`add`/`comment`/`upload`/
`send`/`post`/`put`/`delete`/`append`/`insert`/`merge`/`push`/`reply`/
`share`/`forward`/`schedule`/`launch`/`trigger`), WebFetch URLs, and WebSearch
queries are scanned for secret VALUES (`op://` refs, private-key headers, cloud
tokens, connection strings — the same pattern set as `check-output.sh`). A match
is blocked to stop exfiltration. Practical effect: a GitHub issue/PR write or an
Asana/Drive write whose body contains a real-looking secret is denied — redact
it (e.g. `op://…` → `op-uri`). Read-only MCP tools (bigquery / dagster / dbt
`get_`/`list_`/`search_`) are not scanned. There is no keyword-based URL scanner
— only secret-value shapes match.

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

**Smoke-testing an ADC-auth tool from Bash:** setting
`GOOGLE_APPLICATION_CREDENTIALS=<...credentials.json>` inline (to replicate an
`.mcp.json` env) trips the credentials-JSON sensitive-path block. Omit it — the
binary falls back to default ADC discovery, which resolves the same file.

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

**Non-Bash tool inputs are path-scanned too:** `TodoWrite` / `AskUserQuestion`
text containing a bare `env` (or other sensitive-path token) trips Rule 1 or 3c.
Reword (`environment variable`; avoid cred-suffix tokens like `_KIPPMIAMI`).
Also fires on `mcp__github__*` PR / issue bodies — prose like "staging env" /
"dev env" is denied; write "environment".

**Your own ad-hoc Bash self-blocks on `$UPPER_CASE`:** Rule 7 denies any Bash
command expanding a non-allowlisted uppercase var — including one you define in
that same command (`sc=$(...); echo "${SC}"`). Use lowercase names
(`sc=...; echo "${sc}"`) in throwaway commands.

**BigQuery MCP** — queries must start with SELECT/SHOW/DESCRIBE/WITH; embedded
DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) is blocked. The block
matches the keyword as a substring — including inside a string literal
(`where type = 'Drop'`). Reword to avoid the literal (`like 'Dr%'`).

**Deny messages name the rule.** Every `check-sensitive.sh` denial reads
`❌ check-sensitive.sh Rule N: <what matched>. <what to do instead>.` Follow the
instruction in the message before consulting this file; the two agree.

**Output scanning** (PostToolUse) — redacts tool results containing secret
material (keys, tokens, connection strings, high-entropy strings): every string
in the result becomes `[redacted: secret material]` and an `additionalContext`
note says why. Fires for Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch,
and MCP tools. Does NOT fire for Edit.

**MCP spill files are Bash-unreadable:** a large MCP result that overflows the
context budget dumps to `~/.claude/projects/.../tool-results/`; Bash
(`jq`/`cat`) on that path is denied by the hook. Use a subagent (as the spill
message suggests) or reconstruct the data from prior tool output instead.

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

## Git authentication for new repos

The Codespace `GITHUB_TOKEN` (`ghu_*`) only has access to the repo it was
provisioned for. Pushing to other org repos requires bypassing it:
`GITHUB_TOKEN= git -c credential.helper='!gh auth git-credential' push`

The Codespace token also lacks `project` and org-admin scopes. `gh` calls that
mutate ProjectV2 items/fields fail with "Resource not accessible by integration"
— prefix with `GITHUB_TOKEN=` to fall back to the user's OAuth token (`gho_*`)
which has full scopes.

`gh run rerun` fails the same way as the below: the `ghu_*` token lacks
`workflow` scope, and the `GITHUB_TOKEN=` fallback returns "cannot be retried".
Hand reruns to the user or push a commit to re-trigger.

`gh workflow run` (`workflow_dispatch`) can't be done from the Codespace: the
`ghu_*` token lacks the `workflow` scope (403 "Resource not accessible by
integration"), and emptying it via `GITHUB_TOKEN=` leaves `gh` API calls
unauthenticated. No `mcp__github__*` tool dispatches workflows either — hand it
to the user or the Actions UI. (Pushing a commit that edits a
`deploy-prod-<loc>.yaml` also triggers that location's deploy, since the file is
in its own push-paths.)

## Protected files

Hook scripts, `settings.json`, and `.devcontainer/scripts/` are Edit-denied:
draft the change and hand it to the user. Full procedure, `permissions.deny`
semantics, and the settings-integrity checks load from
`.claude/rules/claude-settings.md` on the first read of one of those files.

If the hook blocks a `git commit -m` message,
`rm -f .claude/scratch/commit-msg.txt`, Write the message there, then
`git commit -F .claude/scratch/commit-msg.txt`. Keep the Bash `description`
generic; it is scanned too.

## Scratch directory

`.claude/scratch/` is gitignored and writable by all tools. Use it for temp
files (commit messages, draft content) that would otherwise be blocked by hooks.
