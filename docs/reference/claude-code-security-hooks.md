# Claude Code Security Hooks

## Reflection

This document captures the design rationale, evolution, and lessons learned from
the security hook system built for Claude Code in the teamster project.

### Problem Statement

Claude Code runs shell commands, reads files, and calls MCP tools on behalf of
the user. The teamster environment contains 1Password-injected secrets, GCP
service account credentials, and environment variables that must never leak into
Claude's context or be exfiltrated. The goal was to create a defense-in-depth
hook system that:

1. Prevents Claude from **reading** sensitive files (`.env`, credentials, keys).
2. Prevents Claude from **modifying** its own guardrails (settings, hooks,
   linter config).
3. Prevents Claude from **leaking** environment variables via shell commands or
   Python introspection.
4. Catches **bypass attempts** (encoding tricks, `__import__`, `importlib`,
   symlinks, path traversal, quote-splitting).
5. Scans **tool output** post-execution for accidentally returned secrets.
6. Restricts **BigQuery MCP** to read-only operations (SELECT/SHOW/DESCRIBE/WITH
   only).

### Architecture

The original design envisioned a three-layer defense model, extended with a
fourth layer after sandbox removal:

| Layer                  | What it covers                                  | Status                    |
| ---------------------- | ----------------------------------------------- | ------------------------- |
| **Hooks**              | All Claude tools (file tools, Bash, MCP)        | Active                    |
| **`permissions.deny`** | Edit on infra paths; Read on system-level paths | Active                    |
| **Sandbox**            | Bash subprocesses (filesystem + network)        | Disabled — non-functional |
| **OS hardening**       | Container-level (tmpfs, caps, sudo)             | Active                    |

The sandbox layer was disabled after empirical verification (see
[Phase 5](#evolution-and-lessons-learned)). Hooks, `permissions.deny`, and OS
hardening are the effective security layers.

#### OS Hardening

Three container-level measures applied via `devcontainer.json` and
`postCreate.sh`:

1. **tmpfs for secrets** — `/etc/secret-volume` is a RAM-backed tmpfs mount (10
   MB, mode 0700). Secrets never touch disk. Injected via 1Password
   (`op inject`) with `umask 077` and `install -m 600` for all output files.
   Template files are validated as non-symlinks before injection.
2. **Capability drops** — `NET_RAW`, `SYS_PTRACE`, and `NET_ADMIN` dropped at
   container start. Prevents packet sniffing, process memory inspection, and
   network configuration changes.
3. **Sudo removal** — `sudo` is available only during `postCreate` for one
   privileged step (`chown` of the tmpfs mount), then permanently deleted. No
   privilege escalation path exists for the container lifetime.

#### Hook System

The hook system consists of three components:

#### 1. PreToolUse Hook — `check-sensitive.sh`

A single bash script invoked before every tool call (Read, Edit, Write, Bash,
Grep, Glob, NotebookEdit, WebFetch, WebSearch, and all MCP tools). It reads the
tool invocation JSON from stdin and applies pattern groups organized in three
sections:

##### Section 1 — All tools, path-based

| #   | Pattern Group                     | Purpose                                                                                                                                             |
| --- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Sensitive file/directory patterns | Block `.env*`, `.ssh`, `.kube`, `*.pem/key/cer`, `secrets.json`, `credentials.json`, `secret-volume`, `.devcontainer/tpl/` — scoped to `no_content` |
| 1b  | File-extension path patterns      | Block `*.cer/key/pem` — scoped to `path_only` to avoid false positives on Python attribute access (e.g., `asset.key`) in Edit/Write content         |
| 1c  | High-risk proc/dev paths          | Block `/proc/*/environ`, `/proc/*/cmdline`, `/dev/fd/` — scoped to `no_content` (all tools)                                                         |

##### Section 2 — Bash only, command-pattern

| #   | Pattern Group               | Purpose                                                                                                               |
| --- | --------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 2   | Hook self-protection        | Block Bash on Claude config, hooks, devcontainer scripts, git hooks, and Trunk config — allow Read/Grep/Glob          |
| 3   | Env variable leakage        | Block `printenv`, `declare -x`, `export -p`, `compgen`, `typeset -x`, `os.environ`, `os.getenv`, `/proc/*/environ`    |
| 3b  | Standalone `set`            | Block bare `set` command (dumps all shell variables); allow `set -flags`                                              |
| 3c  | Standalone `env`            | Block bare `env` command (dumps environment); scoped to `path_only`                                                   |
| 4   | 1Password CLI escalation    | Block `op vault`, `op item`, `op read`, `op document`, `op inject`                                                    |
| 5   | Encoding-based bypass       | Block base64/xxd/printf piped to bash/sh/source; process substitution with decode; reverse bash consuming here-string |
| 5b  | Python runtime construction | Block Python `exec`/`eval` with chr/join/bytes/base64/codecs/fromhex — catches runtime string assembly                |
| 5c  | `__import__` bypass         | Block `__import__` with dangerous modules (os, subprocess, shutil, pty, ctypes, socket, http, urllib, etc.)           |
| 5d  | `importlib` bypass          | Block `importlib` with same dangerous module list — avoids `__import__` check                                         |
| 7   | Shell variable expansion    | Block `$UPPER_CASE` vars not on an allowlist of ~60 safe variables; block `${!prefix*}` indirect expansion            |

##### Section 3 — BigQuery MCP

| #   | Pattern Group             | Purpose                                                                                                                                     |
| --- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 8   | BigQuery DML/export block | For `mcp__bigquery__*` tools: require SELECT/SHOW/DESCRIBE/WITH; deny INSERT/UPDATE/DELETE/MERGE/EXPORT/CREATE/DROP/ALTER/GRANT/REVOKE/CALL |

Key design decisions in the PreToolUse hook:

- **Recursive field extraction**: Uses `jq` to extract all string values from
  `tool_input` via `.. | strings`, catching secrets hidden in nested MCP tool
  schemas.
- **Agent description exclusion**: The Agent tool's `description` field is
  excluded from scanning because it contains natural-language metadata that
  triggers false positives on words like "environment."
- **Path normalization**: Collapses `//`, `/./`, resolves `../` traversals, and
  resolves symlinks via `readlink -f`.
- **Quote/backslash stripping**: Removes `"`, `'`, and `\` before keyword
  matching to defeat quote-splitting bypass (`pr""intenv`).
- **Allowlist over denylist for `$VAR`**: Rather than trying to enumerate every
  dangerous variable, we strip known-safe references and deny anything remaining
  that matches `$UPPER_CASE`.
- **`no_content` scoping**: Rules 1 and 1c use a `no_content` variable that
  excludes Write/Edit body fields (`content`, `new_string`, `old_string`). This
  prevents false positives when writing documentation that references sensitive
  paths (e.g., mentioning `.env` or `secret-volume` in a markdown file) while
  maintaining full protection on `file_path`, `command`, MCP `sql`, and nested
  `tool_input` fields. Rule 1b uses `path_only` (even narrower) to avoid false
  positives on Python attribute access like `asset.key`.

#### 2. PostToolUse Hook — `check-output.sh`

Scans output from Bash, Read, Grep, NotebookEdit, WebFetch, WebSearch, and all
MCP tools for patterns that indicate leaked secrets (Edit is excluded — it does
not produce content that could contain secrets):

- `op://` references (1Password URIs)
- Private key headers (RSA, EC, OPENSSH)
- Google API keys (`AIza...`), OAuth tokens (`ya29.`), `goog_` prefixes
- JWTs (`eyJ...eyJ...`)
- AWS access keys (`AKIA...`)
- Database connection strings (postgres/mysql/mongodb URIs with credentials)
- Service account JSON (`"type": "service_account"`)
- GitHub tokens (`ghp_`, `ghs_`, `ghu_`, `gho_`, `ghr_`, `github_pat_`)
- High-entropy strings (120+ chars of `[A-Za-z0-9+/=_-]`) as a catch-all

The output hook also decodes base64 blobs found in the output and re-scans the
decoded content, catching secrets that were base64-encoded in tool responses.

#### 3. Settings Configuration — `settings.json`

The settings file ties the hooks together with:

- **SessionStart hook**: Sanitizes shell snapshots on session init by stripping
  lines containing `_SECRET`, `_TOKEN`, `_PASSWORD`, etc.
- **PreToolUse (Bash matcher)**: Re-sanitizes shell snapshots before every Bash
  call.
- **PreToolUse (broad matcher)**: Runs `check-sensitive.sh` for all tool types.
- **PostToolUse (output scanner)**: Runs `check-output.sh` for content-producing
  tools.
- **PostToolUse (formatter)**: Runs `trunk fmt` asynchronously after Edit/Write.
- **`permissions.deny`**: Blocks Edit on hook scripts, Claude settings files,
  devcontainer scripts, git hooks, and all Trunk config
  (`/.claude/hooks/**/*.sh`, `/.claude/settings.json`,
  `/.claude/settings.local.json`, `/.devcontainer/scripts/**`, `/.git/hooks/**`,
  `/.trunk/**`, `~/.claude/shell-snapshots/**`). Also blocks Read on
  system-level sensitive paths (`//proc/**`, `//etc/secret-volume/**`,
  `//dev/fd/**`, `/env/**`, `~/.ssh/**`, `~/.kube/**`). These are hard denies —
  no hook involved.
- **`permissions.allow`**: Scoped auto-approvals for git/gh/trunk read commands,
  `Read()` for the workspace and plugins, BigQuery MCP, Dagster MCP, and GKE MCP
  tools.

**Sandbox disabled**: The Claude Code sandbox (bubblewrap) requires
`CAP_SYS_ADMIN` for Linux user namespaces. GitHub Codespaces silently strips
`--cap-add=SYS_ADMIN` from `devcontainer.json` `runArgs` — the capability never
appears in the container's bounding set. `enableWeakerNestedSandbox` also
provides no filesystem or network enforcement in Codespaces. Sandbox
configuration has been removed from `settings.json` entirely. **Hooks,
`permissions.deny`, and OS hardening are the sole enforcement layers.**

### Test Suite

The monolithic `test_hook_security.sh` (591 lines) was split into six focused
test files under `tests/hooks/`:

| File                        | Tests | Coverage                                                                                                                                |
| --------------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `test_sensitive_paths.sh`   | 52    | File patterns (incl. `.kube`), content scanning, quote bypass, path traversal, symlinks, Agent description scoping                      |
| `test_env_protection.sh`    | 60    | printenv/declare/export/compgen/typeset, os.environ, bare `set`, `$VAR` allowlist                                                       |
| `test_bypass_protection.sh` | 71    | 1Password CLI, base64/xxd/printf encoding, process substitution, Python exec/eval construction, `__import__`, importlib, /proc, /dev/fd |
| `test_output_scanner.sh`    | 42    | Secret pattern detection, tool-specific scanning, MCP output, high-entropy boundary (119/120/121 chars)                                 |
| `test_bigquery_mcp.sh`      | 27    | Generic field extraction, nested fields, DML/DDL/export blocking                                                                        |
| `test_self_protection.sh`   | 20    | Hook scripts and Claude config (Bash blocked by hook; Edit/Write blocked by `permissions.deny`)                                         |

Supporting infrastructure:

- **`helpers.sh`**: Shared test helpers (`make_input`, `expect_deny`,
  `expect_allow`, `check_output`, `print_summary`) that build JSON payloads and
  assert hook exit codes.
- **`run_all.sh`**: Runner that discovers and executes all `test_*.sh` files,
  aggregating pass/fail counts.

Total: 272 test cases across the six suites.

### Evolution and Lessons Learned

The work progressed through roughly seven phases:

**Phase 1 — Initial hardening**: Created the hook scripts, established the
settings.json structure, and wrote the first CLAUDE.md documentation for the
access control policies.

**Phase 2 — Bypass discovery**: Each iteration discovered new bypass vectors and
closed them:

- `.env.local`, `.env.production`, `.env.backup` variants
- `op inject` and `op --format json vault list` flag reordering
- `base64 --decode` (long flag variant)
- `eval()` / `exec()` with chr/join/bytes/base64/codecs/fromhex
- Recursive MCP field scanning (nested objects and arrays)
- Output expansion (decoding base64 blobs in tool output)

**Phase 3 — Deep hardening**: Addressed more exotic vectors:

- `importlib.import_module()` as a bypass for `__import__` blocking
- `$VAR` expansion allowlist (instead of trying to block specific var names)
- `${!prefix*}` indirect expansion
- `.git/hooks/` self-protection
- MCP output scanning in the PostToolUse hook
- `set` as a standalone command (dumps all shell variables)

**Phase 4 — Test refactoring**: Split the monolithic test file into six
domain-focused suites with shared helpers, making it easier to run individual
suites and maintain coverage as new patterns are added.

**Phase 5 — Sandbox investigation and removal**: The original design placed
filesystem and network enforcement in a bubblewrap sandbox layer, allowing hooks
to be simplified (Rules 1/1b removed from Bash scope, Rule 6 removed entirely).
This required `CAP_SYS_ADMIN` for user namespace creation. The investigation
timeline:

1. Added bubblewrap + socat to apt install, configured sandbox in settings.json
2. Discovered `CAP_SYS_ADMIN` is not in Docker's default set — added
   `--cap-add=SYS_ADMIN` to `runArgs`
3. Discovered Codespaces silently strips `--cap-add=SYS_ADMIN` — verified via
   `capsh --print` (standard Docker set only, no `cap_sys_admin`)
4. Root cause: OCI seccomp filter gates `CLONE_NEWUSER` on `CAP_SYS_ADMIN`;
   `unshare(CLONE_NEWUSER)` returns `EPERM`
5. Fell back to `enableWeakerNestedSandbox` — ran a verification gate with hooks
   disabled: all `denyRead` paths readable (including `/proc/self/environ` which
   leaked tokens), all `denyWrite` paths writable, no network proxy detected
6. Concluded sandbox provides zero enforcement; retained Rules 1/1b/2 for Bash,
   re-added Rule 1c (renamed from Rule 6, scoped to `no_content`)
7. Removed bubblewrap from apt install, commented out sandbox config in
   settings.json to avoid a misleading safety claim

`--privileged` mode would grant `CAP_SYS_ADMIN` but was rejected as
disproportionate (grants all capabilities). Auto-allow mode was also rejected —
since the sandbox provides no enforcement, auto-allow would remove the only
effective gate (user permission prompts).

**Phase 6 — Gap closure**: Added `.kube` to the sensitive path patterns (Rule 1)
to protect kubeconfig files containing cluster CA certs and auth tokens.

**Phase 7 — permissions.deny refactor**: Moved Edit/Write protection for
infrastructure paths (hook scripts, Claude settings, devcontainer scripts, git
hooks, Trunk config, shell snapshots) from hook Rule 2 into `permissions.deny`
hard-deny rules. Hook Rule 2 now only covers Bash (which `permissions.deny`
cannot block). Added `Read()` hard-deny rules for system-level paths (`/proc`,
`/etc/secret-volume`, `/dev/fd`, `/env`, `~/.ssh`, `~/.kube`). Tightened
`test_self_protection.sh` to reflect the dual-layer enforcement (hook tests for
Bash, `permissions.deny` covers Edit/Write without needing hook tests). Removed
sandbox config from `settings.json` entirely (was already non-functional;
keeping commented-out config was misleading). Added standalone `env` block (Rule
3c) and added GKE MCP tools to the permissions allow list.

### Known Limitations

The hooks are explicitly best-effort, as documented in the script header:

> Bash is Turing-complete so obfuscated commands (base64, variable indirection,
> eval, etc.) cannot be caught by regex.

Real security boundaries remain:

1. **File permissions**: `umask 077` / `chmod 700` on secrets directories.
2. **1Password authentication**: Secrets require `OP_SERVICE_ACCOUNT_TOKEN`
   which is injected at container start, not stored in files.
3. **Shell snapshot sanitization**: Lines with secret-like variable names are
   stripped before Claude sees them.
4. **Capability drops**: `NET_RAW`, `SYS_PTRACE`, `NET_ADMIN` removed at
   container start — OS-level enforcement independent of hooks.
5. **Sudo removal**: No privilege escalation path after container setup
   completes.

The hooks are a **deterrent and safety net**, not a sandbox. They catch
accidental leakage and common attack patterns, but a determined adversary with
full bash access could theoretically construct an undetectable bypass. The hooks
raise the bar significantly while keeping the developer experience frictionless
for legitimate operations.

**No network egress restrictions**: The container can reach any external
endpoint. Codespaces provides outer VM isolation (ephemeral environment, managed
network), but there is no per-container network filtering. If secrets were
leaked into Claude's context, there is no network-level barrier to exfiltration
beyond the output scanner hook.

**Sandbox non-functional**: bubblewrap requires `CAP_SYS_ADMIN` which Codespaces
silently strips. The `enableWeakerNestedSandbox` fallback provides no filesystem
or network enforcement. Sandbox configuration has been fully removed from
`settings.json`. If Codespaces ever starts honoring `--cap-add=SYS_ADMIN`, a
sandbox can be re-added and a verification gate re-run to confirm enforcement
before relaxing hook or `permissions.deny` rules.

### Maintenance

- **Adding a new sensitive pattern**: Add regex to the appropriate numbered
  section in `check-sensitive.sh`, then add test cases to the corresponding test
  file.
- **Adding a safe `$VAR`**: Append to the `safe` variable in pattern 7 of
  `check-sensitive.sh`, then add an `expect_allow` test to
  `test_env_protection.sh`.
- **Adding an output pattern**: Add regex to `check-output.sh`, then add a
  `check_output` test to `test_output_scanner.sh`.
- **Running tests**: `bash tests/hooks/run_all.sh` (or individual suites). Edits
  to test files must be drafted and applied manually due to content scanning
  (the test fixtures contain sensitive pattern strings that trigger the hooks).
