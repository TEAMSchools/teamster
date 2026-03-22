# Codespace Sandbox Hardening — Design Spec

**Date:** 2026-03-20 **Updated:** 2026-03-22 **Status:** Draft

## Overview

Six hardening measures applied to the GitHub Codespaces dev environment:

**OS-level (devcontainer):**

1. **tmpfs for secrets** — `/etc/secret-volume` moves to RAM-backed tmpfs;
   secrets never touch disk
2. **Capability drops** — three dangerous Linux capabilities dropped at
   container start via `runArgs` (NET_RAW, SYS_PTRACE, NET_ADMIN)
3. **Sudo removal** — sudo is available only during `postCreate` for the single
   privileged setup step; removed before the container is handed to the user

**Claude Code sandbox:**

1. **Sandbox mode** — Claude Code's sandboxed bash tool enabled with
   `enableWeakerNestedSandbox` (required because Codespaces blocks unprivileged
   user namespaces); provides OS-level filesystem and network isolation for all
   bash subprocesses
2. **Hook restructuring** — `check-sensitive.sh` reorganized by tool type;
   path-based rules removed from Bash (sandbox owns that) while command-pattern
   rules retained (sandbox cannot cover these)
3. **Output scanning relaxation** — `check-output.sh` no longer scans Edit/Write
   output; Claude is the author of that content, not the reader, and sandbox
   network filtering prevents exfiltration

A seventh code change relocates SFTP transient download files from `env/` to
`/tmp/dagster/`, a side effect of consolidating all secrets into
`/etc/secret-volume`.

Convenience symlinks at the repo root (`secret-volume/`, `dagster-tmp/`) provide
easy access to both locations during development.

---

## Motivation

The existing setup stores secrets as disk-backed files under
`/etc/secret-volume` and `env/.env`. These persist across container restarts and
are accessible to any process with filesystem read access. Additionally, `sudo`
remains available indefinitely, and the container retains capabilities useful
only to attackers (raw sockets, process inspection, network admin).

The hooks (`check-sensitive.sh`, `check-output.sh`) were originally the sole
protection layer. They use regex pattern matching on tool inputs and outputs —
effective but best-effort against obfuscation. This spec adds two reinforcing
layers beneath them.

### Three-layer protection model

| Layer            | What it covers                           | Strengths                                        |
| ---------------- | ---------------------------------------- | ------------------------------------------------ |
| **Hooks**        | All Claude tools (file tools, Bash, MCP) | Covers Claude's own tool use, output scanning    |
| **Sandbox**      | Bash subprocesses (filesystem + network) | OS-level enforcement, can't be bypassed by regex |
| **OS hardening** | Container-level (tmpfs, caps, sudo)      | Protects secrets at rest, limits privilege       |

Each rule lives in the strongest layer that covers it. Redundancy across layers
is only justified when the primary layer is unreliable (e.g., weaker nested
sandbox mode).

These measures raise the bar against:

- Prompt-injected or accidental secret exfiltration via disk reads
- Privilege escalation via unrestricted sudo
- Network-layer attacks via raw socket or interface manipulation
- Claude autonomously reading secrets via bash subprocesses
- Data exfiltration via bash subprocess network access

---

## Change Inventory

| File                                      | Change                                                                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `.devcontainer/devcontainer.json`         | Add one tmpfs mount + four `--cap-drop` flags to `runArgs`                                                                     |
| `.devcontainer/scripts/postCreate.sh`     | Add `bubblewrap socat` to apt install; add `chown`, `mkdir`, `sudo rm` at end; three symlinks                                  |
| `.devcontainer/scripts/inject-secrets.sh` | Remove sudo block; write `.env` to `/etc/secret-volume/.env`                                                                   |
| `src/teamster/libraries/sftp/assets.py`   | Replace `./env/` prefix with `/tmp/dagster/` in all three factory functions                                                    |
| `.gitignore`                              | Add `secret-volume` and `dagster-tmp`                                                                                          |
| `.claude/settings.json`                   | Add `sandbox` configuration block                                                                                              |
| `.claude/hooks/check-sensitive.sh`        | Restructure by tool type; remove path rules for Bash                                                                           |
| `.claude/hooks/check-output.sh`           | Remove Edit and Write from matcher                                                                                             |
| _(audit)_                                 | Verify `grep -r 'env/\.env'` returns only the symlink and `.gitignore`; update any config that resolves symlinks to real paths |

---

## 1. tmpfs Mount

### Configuration

```jsonc
// devcontainer.json
"mounts": [
  "type=tmpfs,destination=/etc/secret-volume,tmpfs-mode=0700,tmpfs-size=10485760"
]
```

- **Size:** 10 MB — holds credential files and `.env`. Will never approach 1 MB
  in practice; 10 MB is headroom.
- **Mode:** `0700` — directory not world-readable at mount time.
- **Ownership:** Docker creates the mount as root. One privileged step in
  `postCreate` transfers ownership to `vscode` (see Section 3).

### Symlinks

`postCreate` creates two convenience symlinks at the repo root:

```bash
ln -sf /etc/secret-volume /workspaces/teamster/secret-volume
ln -sf /etc/secret-volume/.env /workspaces/teamster/env/.env
```

The dagster-tmp/ symlink is for SFTP transient files (see Section 4).

```bash
mkdir -p /tmp/dagster
ln -sf /tmp/dagster /workspaces/teamster/dagster-tmp
```

`env/.env` remains accessible at its existing path — non-Claude processes
(Dagster, dbt, shell scripts) that reference `env/.env` continue to work without
changes. Claude's tool access remains hook-blocked regardless of the symlink.

Both symlink names are added to `.gitignore`.

### Re-injection behavior

- **`.env` re-injection** — works anytime; `inject-secrets.sh` writes as
  `vscode`, no sudo required
- **File-based secrets** (certs, keys) — require container rebuild; these rarely
  change and are written only during initial setup

---

## 2. Capability Drops

```jsonc
// devcontainer.json
"runArgs": [
  "--cap-drop=NET_RAW",
  "--cap-drop=SYS_PTRACE",
  "--cap-drop=NET_ADMIN"
]
```

| Cap          | What it removes                                              |
| ------------ | ------------------------------------------------------------ |
| `NET_RAW`    | Raw socket access — prevents packet sniffing and crafting    |
| `SYS_PTRACE` | Process memory inspection — prevents reading other processes |
| `NET_ADMIN`  | Network config (iptables, interface management)              |

### Why SYS_ADMIN is NOT dropped

`CAP_SYS_ADMIN` must remain in the bounding set for bubblewrap (bwrap) to
function. The Docker/OCI default seccomp profile allows the `clone`/`unshare`
syscalls with `CLONE_NEWUSER` **only when** `CAP_SYS_ADMIN` is present in the
bounding set. Dropping it causes bwrap to fail with "No permissions to create
new namespace", which completely disables the Claude Code sandbox.

This was verified empirically: `kernel.unprivileged_userns_clone = 1` and
`max_user_namespaces = 63954` in the Codespace kernel, but
`unshare(CLONE_NEWUSER)` returns `EPERM` when `SYS_ADMIN` is absent due to the
seccomp filter (`Seccomp: 2`, 1 active filter).

The risk of retaining `SYS_ADMIN` is mitigated by:

- sudo removal after postCreate (no root escalation path)
- The sandbox itself restricts filesystem access for bash subprocesses
- Hooks guard sensitive paths for all Claude tools

No development workflow (uv, Python, Dagster, dbt, GCS/BigQuery API calls, SFTP,
1Password CLI) requires NET_RAW, SYS_PTRACE, or NET_ADMIN.

---

## 3. Sudo Removal

### Why sudo is still needed (briefly)

Docker creates the tmpfs at `/etc/secret-volume` as root. One `chown` transfers
ownership to `vscode` before `inject-secrets.sh` runs. After that, all writes to
`/etc/secret-volume` are unprivileged.

### `postCreate` privileged sequence

```bash
# 1. transfer tmpfs ownership to vscode — only sudo call
sudo chown vscode:vscode /etc/secret-volume

# 2. inject secrets (no sudo inside inject-secrets.sh)
.devcontainer/scripts/inject-secrets.sh

# 3. create convenience symlinks
ln -sf /etc/secret-volume /workspaces/teamster/secret-volume
ln -sf /etc/secret-volume/.env /workspaces/teamster/env/.env
mkdir -p /tmp/dagster
ln -sf /tmp/dagster /workspaces/teamster/dagster-tmp

# 4. remove sudo — must be last privileged step
sudo rm -f /usr/local/bin/sudo /usr/bin/sudo
```

### `inject-secrets.sh` changes

The existing sudo block is removed. Files are written directly as `vscode` using
`install -m 600` instead of `sudo mv`:

```bash
# before (removed):
sudo chown root:root "${TMP_SECRET}"
sudo chmod 600 "${TMP_SECRET}"
sudo mv -f "${TMP_SECRET}" "/etc/secret-volume/${tpl}"

# after:
install -m 600 "${TMP_SECRET}" "/etc/secret-volume/${tpl}"
```

The `.env` injection target changes from `env/.env` to
`/etc/secret-volume/.env`.

### Post-removal behavior

After `postCreate` completes, sudo is permanently unavailable for the lifetime
of the container. Any future privileged operation requires a container rebuild.
Re-injection of `.env` works at any time without sudo.

---

## 4. SFTP Transient File Relocation

SFTP assets currently stage downloaded files at
`./env/{asset_key}/{remote_path}`. With `env/` no longer a general-purpose
staging directory, these move to `/tmp/dagster/{asset_key}/{remote_path}`.

Five `./env/` references across the three factory functions are updated:

- `build_sftp_file_asset` — line 180 (`sftp_get` local path)
- `build_sftp_archive_asset` — line 312 (`sftp_get` local path), line 334
  (`zipfile.extract` output path), line 338 (extracted file path)
- `build_sftp_folder_asset` — line 454 (`sftp_get` local path)

```python
# before
f"./env/{context.asset_key.to_user_string()}/..."

# after
f"/tmp/dagster/{context.asset_key.to_user_string()}/..."
```

Files in `/tmp/dagster/` are disk-backed, persist for the container session, and
are accessible via the `dagster-tmp/` symlink for manual inspection. They are
not secrets and do not require tmpfs.

### Audit: `env/.env` references in dev configs

Search for hardcoded `env/.env` references across the repo. The symlink means
most tools work without changes, but any config that resolves symlinks to their
real path may need updating. Done when `grep -r 'env/\.env'` returns only the
symlink itself and `.gitignore`.

---

## 5. Claude Code Sandbox Configuration

### Sandbox mode selection

With `CAP_SYS_ADMIN` retained (see Section 2), bubblewrap can create user
namespaces and the full sandbox mode should function. The
`enableWeakerNestedSandbox` option is kept as a fallback — if the full sandbox
fails for any reason (e.g., future Codespaces kernel changes), Claude Code falls
back to weaker mode rather than disabling the sandbox entirely.

In full sandbox mode, bubblewrap provides OS-level filesystem isolation for bash
subprocesses, enforcing `denyRead` and `denyWrite` paths at the syscall level.
Network proxy filtering runs outside the sandbox in both modes.

### Sandbox mode

Regular permissions mode (not auto-allow). Sandbox provides OS-level filesystem
and network enforcement, but all bash commands still go through the existing
permission flow. Git and gh write commands (push, pr create, issue create)
remain unlisted in the allow rules and continue to prompt for approval.

Auto-allow mode was rejected because it would auto-approve any sandboxed bash
command, including `git push` if `github.com` is an allowed network domain —
creating an exfiltration vector through a broad allowed domain.

### Configuration

Added to `.claude/settings.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "enableWeakerNestedSandbox": true,
    "filesystem": {
      "denyRead": [
        "~/.ssh",
        "~/.config/gcloud",
        "~/.kube",
        "/etc/secret-volume",
        "./secret-volume",
        "/proc/",
        "/dev/fd/",
        "./.devcontainer/tpl/",
        "./env/"
      ],
      "denyWrite": [
        "./.claude/settings.json",
        "./.claude/settings.local.json",
        "./.claude/hooks/",
        "./.claude/shell-snapshots/",
        "./.devcontainer/scripts/",
        "./.git/hooks/",
        "./.trunk/"
      ]
    }
  }
}
```

Sandbox path prefixes match any path that starts with the prefix string.
Trailing slashes are recommended — `/proc/` matches `/proc/1/environ` but not a
hypothetical `/processor` path. All listed paths use trailing slashes for
directories and no trailing slash for leaf paths (`~/.ssh` matches
`~/.ssh/id_rsa`).

### Path coverage

Sandbox `denyRead` and `denyWrite` use path prefixes, not globs. Pattern-based
sensitive paths (`.env*`, `*.pem`, `*.key`, `*.cer`, `credentials.json`,
`secrets.json`) cannot be expressed as sandbox paths and remain in the hooks for
file tool protection.

| Sandbox path           | What it protects                   |
| ---------------------- | ---------------------------------- |
| `~/.ssh`               | SSH keys and config                |
| `~/.config/gcloud`     | gcloud credentials, ADC, tokens    |
| `~/.kube`              | Kubernetes config and auth cache   |
| `/etc/secret-volume`   | 1Password-injected secrets (tmpfs) |
| `/proc/`               | Process memory, environ, cmdline   |
| `/dev/fd/`             | File descriptor access             |
| `./.devcontainer/tpl/` | Secret templates                   |
| `./secret-volume`      | Symlink to `/etc/secret-volume`    |
| `./env/`               | Symlink dir to secret-volume       |

### Dependency

Bubblewrap and socat must be added to the apt install in `postCreate.sh`:

```bash
sudo apt-get -y install --no-install-recommends sshpass bubblewrap socat
```

---

## 6. Hook Restructuring

### Design principle

Each protection rule lives in one layer. The hooks shift focus to Claude's
autonomous tool use (file tools, MCP) — the threat sandbox cannot cover. Bash
subprocess filesystem access is delegated to the sandbox. Bash command-pattern
rules stay in the hooks because they prevent secrets from entering Claude's
context, which sandbox cannot help with.

### check-sensitive.sh — new structure

The flat list of regex rules is reorganized into three sections by tool type:

**Section 1 — File tools** (Read, Edit, Write, Grep, Glob, NotebookEdit,
WebFetch, WebSearch):

- Rule 1: sensitive path patterns (`.env*`, `.ssh`, `.pem`, `.key`, `.cer`,
  `credentials.json`, `secrets.json`, `secret-volume`, `.devcontainer/tpl/`)
- Rule 1b: file-extension patterns scoped to `path_only`
- Rule 2: self-protection — block writes to hook scripts, settings, config
  (Edit/Write/NotebookEdit only; Read/Grep/Glob still allowed)

**Section 2 — Bash only:**

- Rule 3/3b/3c: env var leakage (`printenv`, `declare -x`, `export -p`, `set`,
  `env`)
- Rule 4: 1Password CLI escalation (`op vault/item/read/document/inject`)
- Rule 5/5a-5d: encoding bypass detection (base64/xxd/printf piped to bash,
  Python exec/eval with chr/join/bytes/base64/codecs, `__import__` and
  `importlib` with sensitive modules)
- Rule 7: `$UPPER_CASE` variable expansion blocking (including `${!prefix*}`
  indirect expansion)

**Section 3 — BigQuery MCP:**

- Rule 8: read-only enforcement (only SELECT/SHOW/DESCRIBE/WITH; deny
  INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/GRANT/REVOKE/CALL/MERGE/EXPORT)

Note: `mcp__bigquery__ask_data_insights` accepts natural language, not SQL. It
is blocked by Rule 8 (input does not start with SELECT/SHOW/DESCRIBE/WITH) and
is also absent from the permissions allow list. This double-gating is
intentional — the tool generates and executes SQL internally without user
review.

### Rules removed

- **Rule 6** (`/proc/*/`, `/dev/fd/`) — removed entirely. Sandbox `denyRead`
  covers bash subprocesses. Claude's file tool permissions already restrict Read
  to project dir and plugins dir, blocking `/proc/` access.

### Rules removed from Bash scope (gated on verification)

Rules 1, 1b, and 2 are removed from Bash scope only after automated testing
confirms the weaker nested sandbox reliably blocks every listed `denyRead` and
`denyWrite` path. If verification fails, these rules remain as defense-in-depth
until sandbox enforcement is confirmed.

- **Rule 1/1b** (sensitive file paths) — sandbox `denyRead` covers bash
  subprocess reads of these paths at OS level
- **Rule 2** (self-protection writes) — sandbox `denyWrite` covers bash
  subprocess writes to these paths at OS level

### check-output.sh — relaxed matcher

The PostToolUse hook matcher changes from:

```text
Bash|Read|Edit|Grep|NotebookEdit|WebFetch|WebSearch|mcp__.*
```

to:

```text
Bash|Read|Grep|NotebookEdit|WebFetch|WebSearch|mcp__.*
```

**Edit removed.** (Write was never in the matcher.) Rationale: when Claude
writes content via Edit, it is the author — the content already exists in
Claude's context. Output scanning this tool only catches false positives (e.g.,
documentation containing example secret patterns like `op://` URIs). Sandbox
network filtering prevents exfiltration of any content Claude has in context via
bash subprocesses.

### No changes

- SessionStart shell-snapshot sanitization hook
- PreToolUse:Bash shell-snapshot sanitization hook
- PostToolUse:Edit|Write trunk fmt hook
- settings.json hook matchers (tool-type branching is inside the scripts)
- Permissions block (existing allow list unchanged)

---

## Testing & Verification

After implementation, verify:

**OS hardening (Sections 1-4):**

1. `docker inspect <container>` shows the tmpfs mount on `/etc/secret-volume`
2. `ls -la /etc/secret-volume` shows `vscode` ownership and mode `700`
3. `inject-secrets.sh` runs without error and all expected files exist in
   `/etc/secret-volume`
4. `env/.env` and `secret-volume/` symlinks resolve correctly
5. `sudo` is not available after `postCreate` completes (`command -v sudo`
   returns nothing)
6. Dagster loads env vars correctly
7. An SFTP asset materialization writes to `/tmp/dagster/` and is accessible via
   `dagster-tmp/`

**Sandbox (Section 5):**

1. `bwrap --ro-bind / / -- echo "bwrap works"` succeeds (confirms user namespace
   creation is allowed by the kernel and seccomp profile)
2. Bash commands inside sandbox cannot read `~/.config/gcloud`, `~/.ssh`,
   `~/.kube`, `/etc/secret-volume`, `/proc/`
3. Bash commands inside sandbox cannot write to `.claude/hooks/`,
   `.claude/settings.json`, `.devcontainer/scripts/`, `.git/hooks/`, `.trunk/`
4. Bash commands requiring non-allowed network domains fall back to permission
   prompt
5. **Verification gate for hook removal:** For each `denyRead` path, confirm
   `cat <path>` inside sandbox returns permission denied. For each `denyWrite`
   path, confirm `touch <path>/test` inside sandbox returns permission denied.
   If any path is not blocked, retain Rules 1/1b/2 for Bash in the hooks.

**Hooks (Section 6):**

1. Hook regression tests pass: `bash tests/hooks/run_all.sh`
2. File tools (Read, Grep) are still blocked from sensitive paths (`.env`,
   `.ssh`, etc.)
3. Edit/Write to `.md` files containing example secret patterns (e.g., `op://`)
   no longer triggers output scanning false positives
4. Bash command-pattern rules still block `printenv`, `set`, `env`, `op` CLI,
   encoding bypasses, and `$VAR` expansion

**Future improvement:** Add an automated sandbox smoke test script that verifies
`bwrap` denies reads/writes to listed paths. Automated regression testing would
catch behavioral changes in future Claude Code versions or Codespaces kernel
updates.

---

## Non-Goals

- Custom seccomp profiles — not configurable in managed Codespaces; the default
  OCI seccomp profile is used, which gates `CLONE_NEWUSER` on `CAP_SYS_ADMIN`
- Sandbox auto-allow mode — rejected due to exfiltration risk via broad allowed
  domains (see Section 5)
- Secret injection without container rebuild — accepted limitation for
  file-based secrets
- `pkexec`/`su` privilege escalation paths — `su` is present but requires root's
  password (not set in the base image); `pkexec` is not installed. Neither is
  addressed further; out of scope for a single-user dev container
