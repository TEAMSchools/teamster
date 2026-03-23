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
   First creation takes a few minutes.

## After the Codespace opens

!!! warning "Allow Automatic Tasks"

    The first time the workspace opens, VS Code will ask:

    > *"This folder has tasks that run automatically when you open this folder.
    > Do you allow automatic tasks to run when you open this folder?"*

    **Click "Allow and Run".** This is required for the automated setup to work.
    If you dismiss or deny this prompt, the setup task will not run and you will
    need to configure everything manually.

The **Setup: Post-Build Init** VS Code task runs automatically when the
workspace opens. It walks you through each step in order:

1. **GCloud Application Default Credentials** — opens a browser for Google
   OAuth. Required for BigQuery, dbt, and all GCP-authenticated tooling.
2. **Claude Code authentication** — opens a browser for Claude login.
3. **Claude Code plugin installation** — installs plugins listed in
   `.claude/settings.json`. Re-runs automatically when the plugin list changes.
4. **dbt dev dataset check** — advises you to run **dbt: Build Init** if your
   personal dev datasets don't exist yet (first-time only).

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
