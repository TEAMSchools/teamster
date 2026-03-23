# VS Code Tasks & Scripts

## Environment Quirks

- `lib/` is globally gitignored — use `shared/` for shell helper libraries
- `GITHUB_USER` is not available in VS Code task shells — derive with
  `gh api user --jq .login` and persist to `~/.bashrc`
- Claude plugin state lives in `~/.claude/plugins/installed_plugins.json` — read
  with `jq` instead of parsing `claude plugins list` output

## GCloud Auth

- `bq` CLI requires `gcloud auth login` (user credentials), not just ADC
- Running `gcloud auth login` before `gcloud auth application-default login` in
  the same script causes "This app is blocked" errors — keep them separate
- `bq ls` paginates at ~50 rows by default — use `--max_results=N` for large
  result sets
