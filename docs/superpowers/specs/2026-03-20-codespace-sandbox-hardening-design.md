# Codespace Sandbox Hardening — Design Spec

**Date:** 2026-03-20 **Status:** Draft

## Overview

Three hardening measures applied to the GitHub Codespaces dev container:

1. **tmpfs for secrets** — `/etc/secret-volume` moves to RAM-backed tmpfs;
   secrets never touch disk
2. **Capability drops** — four dangerous Linux capabilities dropped at container
   start via `runArgs`
3. **Sudo removal** — sudo is available only during `postCreate` for the single
   privileged setup step; removed before the container is handed to the user

A fourth code change relocates SFTP transient download files from `env/` to
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

These measures raise the bar against:

- Prompt-injected or accidental secret exfiltration via disk reads
- Privilege escalation via unrestricted sudo
- Network-layer attacks via raw socket or interface manipulation

The hooks (`check-sensitive.sh`, `check-output.sh`) remain the primary
deterrent; this spec adds OS-level reinforcement.

---

## Change Inventory

| File                                      | Change                                                                                                                                                             |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.devcontainer/devcontainer.json`         | Add one tmpfs mount + four `--cap-drop` flags to `runArgs`                                                                                                         |
| `.devcontainer/scripts/postCreate.sh`     | Add `chown`, `mkdir`, `sudo rm` at end; three symlinks: `secret-volume/ → /etc/secret-volume`, `env/.env → /etc/secret-volume/.env`, `dagster-tmp/ → /tmp/dagster` |
| `.devcontainer/scripts/inject-secrets.sh` | Remove sudo block; write `.env` to `/etc/secret-volume/.env`                                                                                                       |
| `src/teamster/libraries/sftp/assets.py`   | Replace `./env/` prefix with `/tmp/dagster/` in all three factory functions                                                                                        |
| `.gitignore`                              | Add `secret-volume` and `dagster-tmp`                                                                                                                              |
| _(audit)_                                 | Verify `grep -r 'env/\.env'` returns only the symlink and `.gitignore`; update any config that resolves symlinks to real paths                                     |

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

`env/.env` remains accessible at its existing path — existing code and tool
configs that reference `env/.env` continue to work without changes.

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
  "--cap-drop=SYS_ADMIN",
  "--cap-drop=NET_ADMIN"
]
```

| Cap          | What it removes                                                     |
| ------------ | ------------------------------------------------------------------- |
| `NET_RAW`    | Raw socket access — prevents packet sniffing and crafting           |
| `SYS_PTRACE` | Process memory inspection — prevents reading other processes        |
| `SYS_ADMIN`  | Broad system admin (mount, namespace, keyring) — highest-value drop |
| `NET_ADMIN`  | Network config (iptables, interface management)                     |

`SYS_ADMIN` is absent from Docker's default non-privileged cap set already;
dropping it explicitly guards against future `--privileged` drift.

No development workflow (uv, Python, Dagster, dbt, GCS/BigQuery API calls, SFTP,
1Password CLI) requires any of these capabilities.

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

All three factory functions in `src/teamster/libraries/sftp/assets.py` are
updated:

```python
# before
local_filepath=f"./env/{context.asset_key.to_user_string()}/{file_match}"

# after
local_filepath=f"/tmp/dagster/{context.asset_key.to_user_string()}/{file_match}"
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

## Testing & Verification

After implementation, verify:

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
8. Hook tests pass: `bash tests/hooks/run_all.sh`

---

## Non-Goals

- Full kernel-level sandbox (seccomp, AppArmor) — not configurable in managed
  Codespaces
- Network egress firewalling — not available at the Codespaces platform level
- Secret injection without container rebuild — accepted limitation for
  file-based secrets
- `pkexec`/`su` privilege escalation paths — not addressed; out of scope for a
  single-user dev container
