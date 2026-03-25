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

- **`apt-get` permission errors in `postCreate.sh`**: stale root-owned
  directories in `/var/lib/apt/lists/` and `/var/cache/apt/archives/partial/`
  from the image build cause permission denied errors; pre-clean with
  `sudo rm -rf /var/lib/apt/lists /var/cache/apt/archives/partial` — remove the
  directories entirely so `apt-get update` recreates them with correct
  permissions. Do NOT use `apt-get clean` as the pre-clean step — it itself
  fails on the stale permissions.
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
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs. `.vscode/scripts/` is
  **not** hook-protected and can be edited directly.
- **Machine-scoped VS Code settings**: devcontainer features auto-seed
  `/home/vscode/.vscode-remote/data/Machine/settings.json` (e.g., wrong
  `python.defaultInterpreterPath`, `ms-python.autopep8` as Python formatter).
  Workspace settings override these at runtime, but warnings appear during
  `postCreate` before the workspace loads. Patch this file early in
  `postCreate.sh` via `jq` to suppress them.
