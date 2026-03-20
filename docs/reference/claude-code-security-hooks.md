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

The system consists of three components:

#### 1. PreToolUse Hook — `check-sensitive.sh`

A single bash script invoked before every tool call (Read, Edit, Write, Bash,
Grep, Glob, NotebookEdit, WebFetch, WebSearch, and all MCP tools). It reads the
tool invocation JSON from stdin and applies eight pattern groups:

| #    | Pattern Group                     | Purpose                                                                                                                                                                          |
| ---- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Sensitive file/directory patterns | Block `.env*`, `.ssh`, `*.pem/key/cer`, `secrets.json`, `credentials.json`, `secret-volume`, `.devcontainer/tpl/`                                                                |
| 2    | Hook self-protection              | Block Edit/Write/Bash on `.claude/settings.json`, `.claude/hooks/`, `.claude/shell-snapshots/`, `.devcontainer/scripts/`, `.git/hooks/`, `.trunk/` config — allow Read/Grep/Glob |
| 3    | Environment variable leakage      | Block `printenv`, `declare -x`, `export -p`, `compgen`, `os.environ`, `os.getenv`, `/proc/*/environ`, bare `env`, bare `set` (not `set -flags`)                                  |
| 4    | 1Password CLI escalation          | Block `op vault`, `op item`, `op read`, `op document`, `op inject`                                                                                                               |
| 5    | Encoding-based bypass             | Block base64/xxd/printf piped to bash/sh/source, process substitution, Python exec/eval with chr/join/bytes/base64/codecs/fromhex                                                |
| 5c/d | Python import bypass              | Block `__import__` and `importlib` with dangerous modules (os, subprocess, shutil, pty, ctypes, socket, http, urllib, multiprocessing, signal)                                   |
| 6    | /proc and /dev/fd access          | Broad block on `/proc/*/` and `/dev/fd/`                                                                                                                                         |
| 7    | Shell variable expansion          | Block `$UPPER_CASE` vars not on an allowlist of ~60 safe variables; block `${!prefix*}` indirect expansion                                                                       |
| 8    | BigQuery DML/export block         | For `mcp__bigquery__*` tools: require SELECT/SHOW/DESCRIBE/WITH, deny INSERT/UPDATE/DELETE/MERGE/EXPORT/CREATE/DROP/ALTER/GRANT/REVOKE/CALL                                      |

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

#### 2. PostToolUse Hook — `check-output.sh`

Scans output from Bash, Read, Edit, Grep, NotebookEdit, WebFetch, WebSearch, and
all MCP tools for patterns that indicate leaked secrets:

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
- **Permissions allowlist**: Scoped `Bash()` permissions for git/gh/trunk/uv,
  `Read()` for the workspace and plugins, specific `WebFetch` domains, and MCP
  tools.

### Test Suite

The monolithic `test_hook_security.sh` (591 lines) was split into six focused
test files under `tests/hooks/`:

| File                        | Tests | Coverage                                                                                                                                |
| --------------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `test_sensitive_paths.sh`   | 26    | File patterns, content scanning, quote bypass, path traversal, symlinks, Agent description scoping                                      |
| `test_env_protection.sh`    | 40    | printenv/declare/export/compgen/typeset, os.environ, bare `set`, `$VAR` allowlist                                                       |
| `test_bypass_protection.sh` | 48    | 1Password CLI, base64/xxd/printf encoding, process substitution, Python exec/eval construction, `__import__`, importlib, /proc, /dev/fd |
| `test_output_scanner.sh`    | 27    | Secret pattern detection, tool-specific scanning, MCP output, high-entropy boundary (119/120/121 chars)                                 |
| `test_bigquery_mcp.sh`      | 19    | Generic field extraction, nested fields, DML/DDL/export blocking                                                                        |
| `test_self_protection.sh`   | 18    | Settings, hooks, shell-snapshots, .devcontainer/scripts, .git/hooks, .trunk config                                                      |

Supporting infrastructure:

- **`helpers.sh`**: Shared test helpers (`make_input`, `expect_deny`,
  `expect_allow`, `check_output`, `print_summary`) that build JSON payloads and
  assert hook exit codes.
- **`run_all.sh`**: Runner that discovers and executes all `test_*.sh` files,
  aggregating pass/fail counts.

Total: ~178 test cases across the six suites.

### Evolution and Lessons Learned

The work progressed through roughly four phases:

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

The hooks are a **deterrent and safety net**, not a sandbox. They catch
accidental leakage and common attack patterns, but a determined adversary with
full bash access could theoretically construct an undetectable bypass. The hooks
raise the bar significantly while keeping the developer experience frictionless
for legitimate operations.

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
