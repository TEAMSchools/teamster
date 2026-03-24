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

## GCloud Auth

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

## Claude Auth

- Check Claude auth with `"${CLAUDE}" auth status | grep -q '"loggedIn": true'`;
  flag-file guards for Claude auth are redundant and produce false "not logged
  in" errors when the flag is missing — check auth directly instead
