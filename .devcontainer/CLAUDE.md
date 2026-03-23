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
  `Ctrl+Shift+P` → `Tasks: Run Task`

## Secret Injection

**`inject-secrets.sh`**: manually run to inject 1Password secrets into the
environment. Required for Dagster development; not needed for SQL-only work. Run
after container start if env vars or secrets are missing.

## Quirks

- **`sudo` removed**: at the end of `postCreate.sh` — privileged setup (gcloud
  components, Helm) must go in `postCreate.sh`, not later. To add new
  components, update `postCreate.sh` and rebuild the container.
- **`--cap-add` stripped**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work. Hooks
  are the sole enforcement layer for path-based access control.
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs.
