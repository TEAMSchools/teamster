# CLAUDE.md — `.devcontainer/`

Container configuration for Codespace and local development.

## Setup Lifecycle

- **`postCreate.sh`** runs once on container creation — installs dependencies,
  sets up GCP auth, removes `sudo`
- **`postStart.sh`** runs on every container start — refreshes GCP ADC, Claude
  auth, VS Code tasks. Keep it idempotent.
- **Post-build VS Code task**: "Setup: Post-Build Init" runs automatically on
  folder open after a rebuild — handles GCloud ADC, Claude auth, plugin
  installation, and dbt dev dataset checks. Individual tasks available via
  `Ctrl+Shift+P` → `Tasks: Run Task`. The task polls with `pgrep` until
  `postCreate.sh`/`postStart.sh` finish — VS Code fires `folderOpen` before they
  complete, so this guard is intentional; do not remove it.

## Secret Injection

**`inject-secrets.sh`**: manually run to inject 1Password secrets into the
environment. Required for Dagster development; not needed for SQL-only work. Run
after container start if env vars or secrets are missing.

- **Adding a new secret**: update **both** the symlink validation loop and the
  injection `for` loop — omitting either silently skips the secret.

## 1Password CLI Commands

- **`op inject`** — replaces `op://` references in template files; used for
  `.env.tpl` and other templates with embedded secret URIs
- **`op read`** — reads a single secret or file attachment by `op://` URI;
  supports `--out-file` for binary output; use for multi-attachment items (e.g.,
  `op read "op://vault/item/filename" --out-file path`)
- **`op document get`** — downloads an item's document attachment by item
  name/UUID (not `op://` URIs); no `--file-name` flag exists, so it cannot
  select among multiple attachments — use `op read` instead

## Claude Code Auth in Codespaces

- The CLI binary detects `op` on `$PATH` and tries to use it as a credential
  backend — `OP_SERVICE_ACCOUNT_TOKEN` is set to a dummy value after secret
  injection (`postStart.sh`) to make `op` fail fast instead of prompting
- `CLAUDE_CODE_OAUTH_TOKEN` (not `ANTHROPIC_AUTH_TOKEN`) is the correct env var
  for OAuth token auth — use as a personal Codespace secret to bypass credential
  store entirely
- GitHub Actions workflows use `claude_code_oauth_token` input (not
  `anthropic_api_key`)

## Quirks

- **Claude's Bash shell lacks injected secrets**: `inject-secrets.sh` secrets
  (e.g., `ILLUMINATE_DB_DRIVERNAME`) are only available in the user's terminal
  session, not in Claude Code's Bash tool. Commands requiring these env vars
  (e.g., `uv run dagster definitions validate`) must be run by the user.
- **`apt-get` and `DAC_OVERRIDE`**: devcontainer features (1Password,
  gcloud-cli) run `apt-get update` during `docker build`, leaving stale files in
  `/var/lib/apt/lists/partial/` owned by `_apt:root` with mode `0700`.
  `--cap-drop=DAC_OVERRIDE` in `runArgs` would prevent root from accessing these
  directories at runtime — do NOT add it back. `DAC_OVERRIDE` is safe to keep
  because `sudo` is removed at the end of `postCreate.sh`, making the capability
  irrelevant after setup.
- **`sudo` removed**: at the end of `postCreate.sh` — privileged setup (gcloud
  components, Helm) must go in `postCreate.sh`, not later. To add new
  components, update `postCreate.sh` and rebuild the container.
- **`/etc/secret-volume` tmpfs permissions**: mounted `0777` (world-writable) so
  `inject-secrets.sh` can write to it on every start without sudo. Individual
  secret files are written `600` (owner-read-only), so only the `vscode` user
  can read their contents. `uid`/`gid` mount options were not used — they are
  not supported on all Codespaces hosts.
- **`--cap-add` stripped**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work. Hooks
  are the sole enforcement layer for path-based access control.
- **dbt Power User extension**: activates on
  `workspaceContains:**/dbt_project.yml` and auto-runs `dbt deps` (controlled by
  `dbt.installDepsOnProjectInitialization`, default `true`) and `dbt parse` (not
  configurable) on startup. Risk: extension may activate before `uv sync`
  installs dbt-core. If `dbt deps` runs in `postCreate.sh`, set
  `dbt.installDepsOnProjectInitialization` to `false` to avoid duplicate work.
- **dbt Power User project scanning**: `dbt.allowListFolders` restricts which
  paths the extension scans for `dbt_project.yml` — uses `startsWith` matching.
  The extension also has a built-in `notInDBtPackages` filter. Manifest is read
  from `target/` via Python bridge, not VS Code file watcher, so
  `files.watcherExclude` on `target/` doesn't break it.
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs. `.vscode/scripts/` is
  **not** hook-protected and can be edited directly.
- **Machine-scoped VS Code settings**: devcontainer features auto-seed
  `/home/vscode/.vscode-remote/data/Machine/settings.json` (e.g., wrong
  `python.defaultInterpreterPath`, `ms-python.autopep8` as Python formatter).
  Workspace settings override these at runtime, but warnings appear during
  `postCreate` before the workspace loads. Patch this file early in
  `postCreate.sh` via `jq` to suppress them.
