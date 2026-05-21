# Remove Startup Secret Injection

## Problem

`inject-secrets.sh` runs at container start (postCreate + postStart), writing a
rendered `.env` file and five file-based secrets to `/etc/secret-volume/`. This
means secrets are on disk for the entire container lifetime even when not in
use.

## Goal

Remove all startup secret injection. Replace with on-demand 1Password calls
triggered by pytest, so secrets are only fetched when integration tests actually
run. No changes to `src/` or production (`.k8s/`) code.

## Constraints

- `src/` is unchanged — resource constructors keep receiving the same values.
- Production (GKE) is unchanged — Kubernetes-mounted secrets at
  `/etc/secret-volume/` continue as-is.
- Dev tooling (integration tests) may break during migration and will be fixed
  as part of this work.
- Claude Code must not gain access to secrets — current security posture is
  maintained or improved.

## Design

### 1. Delete `inject-secrets.sh`

Remove `.devcontainer/scripts/inject-secrets.sh` entirely.

### 2. Modify `postCreate.sh`

Remove:

- `chmod 755 .devcontainer/scripts/inject-secrets.sh`
- `chmod 600 .devcontainer/tpl/*`
- `.devcontainer/scripts/inject-secrets.sh` call
- `ln -sfn /etc/secret-volume/.env /workspaces/teamster/env/.env` (no `.env`
  file to symlink)

Keep:

- tmpfs permission fix (`sudo chmod 755 /etc/secret-volume`,
  `sudo chown vscode:vscode /etc/secret-volume`)
- `ln -sfn /etc/secret-volume /workspaces/teamster/secret-volume` (file-based
  secrets still land here)
- `ln -sfn /tmp/dagster /workspaces/teamster/dagster-tmp`
- `mkdir -p ./env` and `chmod 700 ./env` (directory still exists, just empty)

Add:

- Save `OP_SERVICE_ACCOUNT_TOKEN` to `/etc/secret-volume/.op-token` with 600
  permissions, then revoke the env var. This runs before `sudo rm` removes sudo
  at the end of the script.

```bash
# save 1Password token for on-demand use, then revoke from environment
echo "${OP_SERVICE_ACCOUNT_TOKEN}" > /etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token
```

### 3. Modify `postStart.sh`

Remove:

- `.devcontainer/scripts/inject-secrets.sh` call
- All `OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection` lines
- All `OP_CONNECT_TOKEN=revoked-after-injection` lines

Add:

- Revoke `OP_SERVICE_ACCOUNT_TOKEN` and `OP_CONNECT_TOKEN` from future shell
  sessions (same pattern as today, just no longer gated on inject success).

```bash
# revoke 1Password tokens from interactive shells
echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >> /home/vscode/.bashrc
echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >> /home/vscode/.profile
echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >> /home/vscode/.bashrc
echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >> /home/vscode/.profile
```

### 4. Root `conftest.py` — on-demand secret fetching

A new `/workspaces/teamster/conftest.py` with a session-scoped autouse fixture
that runs once per pytest session:

1. Reads `/etc/secret-volume/.op-token` to get the 1Password service account
   token.
2. Calls `op run --env-file=.devcontainer/tpl/.env.tpl -- env` with the token
   set in the subprocess environment. Parses stdout to extract `KEY=VALUE` pairs
   and injects them into `os.environ`.
3. Calls `op read` for each file-based secret, writing to `/etc/secret-volume/`:
   - `adp_wfn_api.cer` (vault: "Data Team", item: "ADP Workforce Now API")
   - `adp_wfn_api.key` (vault: "Data Team", item: "ADP Workforce Now API")
   - `1password-credentials.json` (vault: "Data Team", item: "TEAMster 1Password
     Credentials File")
   - `deanslist_api_key_map.yaml` (vault: "Data Team", item: "DeansList API")
   - `id_rsa_egencia` (vault: "Data Team", item: "Egencia SFTP")

4. File permissions set to 600 after each write.

Note: `tests/CLAUDE.md` currently says "No global `conftest.py`." This will be
updated to document this exception — the conftest has a narrow scope (secret
bootstrapping only, no shared fixtures).

### 5. Hook hardening

**`check-sensitive.sh` Rule 4** — add `run` to the blocked `op` subcommand list:

```bash
# before
\bop\b.*\b(vault|item|read|document|inject)\b
# after
\bop\b.*\b(vault|item|read|run|document|inject)\b
```

### 6. Hook test updates

**`tests/hooks/test_bypass_protection.sh`** — add test case for `op run`:

```bash
expect_deny_exit0 "op run blocked" \
  bash .claude/hooks/check-sensitive.sh Bash '{"command":"op run --env-file=.env.tpl -- env"}'
```

Remove or update any test cases that reference `inject-secrets.sh` if they
become stale.

### 7. `.vscode/settings.json`

Remove `"python.envFile": "${workspaceFolder}/env/.env"` — no `.env` file
exists. Env vars are injected by the conftest at runtime.

### 8. `.env.tpl`

Stays as-is in `.devcontainer/tpl/`. Repurposed as the `op run --env-file`
template. No longer consumed by `op inject`.

## Files changed

| File                                      | Action |
| ----------------------------------------- | ------ |
| `.devcontainer/scripts/inject-secrets.sh` | Delete |
| `.devcontainer/scripts/postCreate.sh`     | Modify |
| `.devcontainer/scripts/postStart.sh`      | Modify |
| `conftest.py`                             | Create |
| `.claude/hooks/check-sensitive.sh`        | Modify |
| `tests/hooks/test_bypass_protection.sh`   | Modify |
| `.vscode/settings.json`                   | Modify |
| `tests/CLAUDE.md`                         | Modify |

## What stays unchanged

- All `src/` code
- `.k8s/` production setup
- `devcontainer.json` (tmpfs mount stays)
- `.devcontainer/tpl/.env.tpl` (repurposed, not modified)
- All `permissions.deny` rules in `.claude/settings.json`

## Security posture

| Concern                       | Mitigation                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| Token in Claude's environment | Revoked in `.bashrc`/`.profile` as today                                           |
| Token on disk                 | `/etc/secret-volume/.op-token` — blocked by `Read(//etc/secret-volume/**)` + hooks |
| `op run` via Claude's Bash    | Blocked by Rule 4 (new `run` subcommand)                                           |
| File-based secrets on tmpfs   | Same path protection as today: deny rules + hook path patterns                     |
| Pytest output leaking secrets | `check-output.sh` scans Bash output for secret patterns                            |
| `.env.tpl` readable by Claude | Blocked by `Read(/.devcontainer/tpl/**)`                                           |
