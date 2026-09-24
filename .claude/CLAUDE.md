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
behavior; the hook protocol (exit codes, JSON shapes) and the context-injection
hook are in `.claude/rules/claude-settings.md`, which loads on a hook read.

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
`/proc/*/environ`, and secret-shaped fixtures (1Password refs that name a vault
— the bare `op://` scheme passes — and key headers; these also trip
`check-output.sh` on the _response_). Reword/backtick them, or keep literal
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

**Deny messages name the rule.** Every `check-sensitive.sh` denial reads
`❌ check-sensitive.sh Rule N: <what matched>. <what to do instead>.` Follow the
instruction in the message before consulting this file; the two agree.

**Output scanning** (PostToolUse) — redacts tool results containing secret
material (keys, tokens, connection strings, high-entropy strings): every string
in the result becomes `[redacted: secret material]` and an `additionalContext`
note says why. Fires for Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch,
and MCP tools. Does NOT fire for Edit.

**MCP spill files are Bash-readable — read them directly, never dispatch a
subagent.** A large MCP result that overflows the context budget dumps to
`~/.claude/projects/<proj>/<session>/tool-results/<tool>-<ts>.txt`, shaped
`{result: string}` where `result` is itself a JSON string. No hook blocks that
path: Rule 2's protected set is `settings.json`, `settings.local.json`,
`hooks/*.sh` and `shell-snapshots/`, none of which match `.claude/projects/`.
Extract with `jq -r '.result' <file> | jq '<filter>'`. The spill message itself
suggests a subagent — ignore that; verified 2026-09-16 after following the old
"Bash-unreadable" note here burned a ~42k-token dispatch to run one `jq length`.

## Protected files

Hook scripts, `settings.json`, and `.devcontainer/scripts/` are Edit-denied:
draft the change and hand it to the user. Full procedure, `permissions.deny`
semantics, and the settings-integrity checks load from
`.claude/rules/claude-settings.md` on the first read of one of those files.

If the hook blocks a `git commit -m` message, Write the message into your
SESSION scratchpad (absolute path given in the system prompt), one file per
commit — `<scratchpad>/commit-msg-<slug>.txt` — then
`git commit -F <that path>`. What makes this work is that Write's `content` is
scan-exempt and no hook rule covers the scratchpad; the specific path is
otherwise incidental. Never use a shared fixed path like
`.claude/scratch/commit-msg.txt`: `.claude/scratch/` is per-checkout, so
concurrent sessions in one worktree overwrite each other, and the old `rm -f`
remedy destroys another session's pending message. Worse, a stale file makes
Write fail while a batched `git commit -F` still runs — committing the OTHER
session's message. Keep the Bash `description` generic; it is scanned too.

## Scratch directory

`.claude/scratch/` is gitignored and writable by all tools, but it is shared per
checkout — every session working that checkout sees the same files. Use it only
for temp files that must live IN the checkout, such as the hook-probe harnesses
in `.claude/hooks/CLAUDE.md`, and give each a distinctive name. Everything else
goes in the session scratchpad.
