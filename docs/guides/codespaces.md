# GitHub Codespaces

The devcontainer is pre-configured for
[GitHub Codespaces](https://github.com/features/codespaces) — no local setup
required.

## Prerequisites

Set **VS Code Desktop** as your default Codespaces editor:

1. Go to
   [github.com/settings/codespaces](https://github.com/settings/codespaces).
2. Under **Editor preference**, select **Visual Studio Code**.
3. Save.

This ensures Codespaces open in VS Code Desktop (with full extension support)
rather than the browser editor.

## Creating a Codespace

1. On the repository page, click **Code → Codespaces → Create codespace on
   main** (or your branch).
2. Select the **4-core / 16 GB** machine type.
3. Wait for the container to finish building. `postCreate.sh` runs
   automatically: installs dependencies, bootstraps all dbt projects
   (`dbt deps` + `dbt parse` in parallel), and injects secrets from 1Password.
   First creation takes a few minutes. VS Code may show a Python interpreter
   warning during this phase — the base container image seeds a machine-scoped
   setting pointing to `/usr/local/bin/python` before the project venv exists.
   `postCreate.sh` overwrites that setting early in its run, so the warning is
   transient and resolves on its own without any action needed.

## After the Codespace opens

!!! warning "Allow Automatic Tasks"

    The first time the workspace opens, VS Code will ask:

    > *"This folder has tasks that run automatically when you open this folder.
    > Do you allow automatic tasks to run when you open this folder?"*

    **Click "Allow and Run".** This is required for the automated setup to work.
    If you dismiss or deny this prompt, the setup task will not run. To fix it,
    add `"task.allowAutomaticTasks": "on"` to your local VS Code **User
    Settings** (++ctrl+shift+p++ → **Open User Settings (JSON)**), then reopen
    the Codespace.

The **Setup: Post-Build Init** VS Code task runs automatically when the
workspace opens. It walks you through each step in order:

1. **GCloud Application Default Credentials** — opens a browser for Google
   OAuth. Required for BigQuery, dbt, and all GCP-authenticated tooling.
2. **Claude Code authentication** — opens a browser for Claude login.
3. **Claude Code plugin installation** — installs plugins listed in
   `.claude/settings.json`. Re-runs automatically when the plugin list changes.
4. **dbt dev dataset reminder** — prints a note about running **dbt: Build
   Init** for first-time setup.

On subsequent opens (restarts, reconnects), the task re-checks each step and
skips anything already configured.

**Dismiss VS Code extension prompts** — all required extensions are already
configured in `devcontainer.json`; dismiss any extension install prompts VS Code
shows.

**Wait for dbt Power User to finish parsing** — the extension parses all
projects in the background, which pegs CPU and makes the extension unresponsive
until complete. Use `htop` to monitor; wait for CPU to settle before using the
extension. This is also the most common cause of "extension not responding"
errors.

**Reload the window** once background processes finish (++ctrl+shift+p++ →
**Developer: Reload Window**) for a clean editor state.

## First-time dbt setup

If this is your first Codespace, you need to build your personal dev datasets in
BigQuery. Run the **dbt: Build Init** task:

1. ++ctrl+shift+p++ → **Tasks: Run Task** → **dbt: Build Init**
2. Select a project (or **all** for the full build).

Regional projects (Camden, Miami, Newark, Paterson) build in parallel; kipptaf
builds last since it depends on them.

## Manual tasks

Individual setup steps are also available via ++ctrl+shift+p++ → **Tasks: Run
Task**:

| Task                              | When to use                          |
| --------------------------------- | ------------------------------------ |
| GCloud: Application Default Login | Re-authenticate after token expiry   |
| Claude: Login                     | Re-authenticate Claude Code          |
| Claude: Install Plugins           | Manually re-install project plugins  |
| dbt: Build Init                   | Rebuild dev datasets (pick projects) |

## Subsequent sessions

`postStart.sh` runs automatically on resume (updates uv, syncs dependencies).
The setup task re-checks auth and plugin state — you only need to
re-authenticate if credentials have expired.

## Container Internals

### Setup Lifecycle

- **`postCreate.sh`** runs once on container creation — installs dependencies,
  sets up GCP auth, removes `sudo`
- **`postStart.sh`** runs on every container start — refreshes GCP ADC, Claude
  auth, VS Code tasks. Keep it idempotent.
- The "Setup: Post-Build Init" task polls with `pgrep` until
  `postCreate.sh`/`postStart.sh` finish — VS Code fires `folderOpen` before they
  complete, so the guard is intentional; do not remove it.

### Secret Injection

`inject-secrets.sh`: manually run to inject 1Password secrets into the
environment. Required for Dagster development; not needed for SQL-only work. Run
after container start if env vars or secrets are missing.

- **Adding a new secret**: update **both** the symlink validation loop and the
  injection `for` loop — omitting either silently skips the secret.

### 1Password CLI Commands

- **`op inject`** — replaces `op://` references in template files; used for
  `.env.tpl` and other templates with embedded secret URIs
- **`op read`** — reads a single secret or file attachment by `op://` URI;
  supports `--out-file` for binary output; use for multi-attachment items (e.g.,
  `op read "op://vault/item/filename" --out-file path`)
- **`op document get`** — downloads an item's document attachment by item
  name/UUID (not `op://` URIs); no `--file-name` flag exists, so it cannot
  select among multiple attachments — use `op read` instead

### GCloud Authentication

ADC in Codespaces works via user-impersonation of the service account
`codespaces@teamster-332318.iam.gserviceaccount.com`. Access is split into two
independent layers:

- **Developer access**: all members of `teamster-analysts@apps.teamschools.org`
  are granted `roles/iam.serviceAccountTokenCreator` on the SA, which allows
  them to impersonate it via `--impersonate-service-account`
- **SA permissions**: `codespaces@` has its own direct IAM bindings on the
  project — it is **not** a member of `teamster-analysts@` and does not inherit
  group roles. This prevents a self-impersonation loop and keeps the SA's
  permissions explicitly auditable in IAM.

To grant a new developer access: add them to
`teamster-analysts@apps.teamschools.org`.

??? note "GCloud quirks"

    - To check if ADC is valid, use
      `gcloud auth application-default print-access-token`; `gcloud auth list`
      only checks user accounts, not ADC — they're independent
    - `bq` CLI requires `gcloud auth login` (user credentials), not just ADC
    - Running `gcloud auth login` before
      `gcloud auth application-default login` in the same script causes "This
      app is blocked" errors — keep them separate
    - `bq ls` paginates at ~50 rows by default — use `--max_results=N` for
      large result sets
    - `gcloud auth application-default login` doesn't work in Codespaces — the
      localhost OAuth callback can't reach the container.
      `gcloud-application-default-login.sh` uses
      `--impersonate-service-account=codespaces@teamster-332318.iam.gserviceaccount.com`
      to work around this; the user must have
      `roles/iam.serviceAccountTokenCreator` on that SA
    - The default gcloud OAuth client blocks `drive.*` scopes — never add them
      to `gcloud auth application-default login` without
      `--impersonate-service-account`
    - `gcloud auth application-default set-quota-project` fails with
      impersonated credentials — use `--billing-project` flag on the login
      command instead

### Claude Code Setup

- `CLAUDE_CODE_OAUTH_TOKEN` (not `ANTHROPIC_AUTH_TOKEN`) is the correct env var
  for OAuth token auth — use as a personal Codespace secret to bypass credential
  store entirely
- GitHub Actions workflows use `claude_code_oauth_token` input (not
  `anthropic_api_key`)
- The CLI detects `op` on `$PATH` and tries to use it as a credential backend —
  `OP_SERVICE_ACCOUNT_TOKEN` is set to a dummy value after secret injection
  (`postStart.sh`) to make `op` fail fast instead of prompting
- `claude-plugins-official` must be listed in `.claude/settings.json`
  `extraKnownMarketplaces` (pointing to `anthropics/claude-plugins-official`) so
  `claude-install-plugins.sh` explicitly refreshes it via
  `marketplace add --scope project` before installs run — omitting it causes
  "Plugin not found in marketplace" errors for all `*@claude-plugins-official`
  plugins
- Check Claude auth with `"${CLAUDE}" auth status | grep -q '"loggedIn": true'`;
  flag-file guards are redundant and produce false "not logged in" errors —
  check auth directly
- On a fresh rebuild the Claude Code extension may not be installed when
  `folderOpen` fires; `$CLAUDE` will be empty — poll for the binary rather than
  silently skipping

### Container Quirks

- **`apt-get` and `DAC_OVERRIDE`**: devcontainer features run `apt-get update`
  during `docker build`, leaving stale files in `/var/lib/apt/lists/partial/`
  owned by `_apt:root` with mode `0700`. `--cap-drop=DAC_OVERRIDE` would prevent
  root from accessing these directories at runtime — do NOT add it back.
  `DAC_OVERRIDE` is safe to keep because `sudo` is removed at the end of
  `postCreate.sh`, making the capability irrelevant after setup.
- **`sudo` removed**: at the end of `postCreate.sh` — privileged setup (gcloud
  components, Helm) must go in `postCreate.sh`, not later. To add new
  components, update `postCreate.sh` and rebuild the container.
- **`/etc/secret-volume` tmpfs permissions**: mounted `0777` (world-writable) so
  `inject-secrets.sh` can write to it on every start without sudo. Individual
  secret files are written `600` (owner-read-only), so only the `vscode` user
  can read their contents. `uid`/`gid` mount options were not used — they are
  not supported on all Codespaces hosts.
- **`--cap-add` stripped**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work.
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
