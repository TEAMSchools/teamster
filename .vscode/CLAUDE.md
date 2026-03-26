# VS Code Tasks & Scripts

## Environment Quirks

- `lib/` is globally gitignored — use `shared/` for shell helper libraries
- `task.allowAutomaticTasks` has application scope — cannot be set in workspace
  settings or `devcontainer.json` customizations; must go in the user's local VS
  Code User Settings
- `GITHUB_USER` is not available in VS Code task shells — derive with
  `gh api user --jq .login` and persist to `~/.bashrc`
- Claude plugin state lives in `~/.claude/plugins/installed_plugins.json` — read
  with `jq` instead of parsing `claude plugins list` output
- VS Code task shells do not inherit `~/.local/bin` in PATH — `uv` is not
  available unless you `source "${HOME}/.local/bin/env"` first

## Task: Update Dependencies

`update-dependencies.sh` replaces `scripts/update.py`. Creates a dated branch,
runs `uv lock --upgrade`, `uv sync`, `trunk upgrade -y`, `dbt deps --upgrade`
for all 15 dbt projects, then commits. Branch name:
`<user>/chore/update-dependencies-<YYYY-MM-DD>`.

## GCloud Auth

### Access Model

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

- To check if ADC is valid, use
  `gcloud auth application-default print-access-token`; `gcloud auth list` only
  checks user accounts, not ADC — they're independent
- `bq` CLI requires `gcloud auth login` (user credentials), not just ADC
- Running `gcloud auth login` before `gcloud auth application-default login` in
  the same script causes "This app is blocked" errors — keep them separate
- `bq ls` paginates at ~50 rows by default — use `--max_results=N` for large
  result sets
- `gcloud auth application-default login` doesn't work in Codespaces — the
  localhost OAuth callback can't reach the container.
  `gcloud-application-default-login.sh` uses
  `--impersonate-service-account=codespaces@teamster-332318.iam.gserviceaccount.com`
  to work around this; the user must have `roles/iam.serviceAccountTokenCreator`
  on that SA
- The default gcloud OAuth client blocks `drive.*` scopes — never add them to
  `gcloud auth application-default login` without
  `--impersonate-service-account`
- `gcloud auth application-default set-quota-project` fails with impersonated
  credentials — use `--billing-project` flag on the login command instead

## Claude Plugins

- `claude-plugins-official` must be listed in `.claude/settings.json`
  `extraKnownMarketplaces` (pointing to `anthropics/claude-plugins-official`) so
  `claude-install-plugins.sh` explicitly refreshes it via
  `marketplace add --scope project` before installs run — omitting it causes
  "Plugin not found in marketplace" errors for all `*@claude-plugins-official`
  plugins

## Claude Auth

- Check Claude auth with `"${CLAUDE}" auth status | grep -q '"loggedIn": true'`;
  flag-file guards for Claude auth are redundant and produce false "not logged
  in" errors when the flag is missing — check auth directly instead
- On a fresh rebuild the Claude Code extension may not be installed when
  `folderOpen` fires; `$CLAUDE` will be empty — poll for the binary rather than
  silently skipping
