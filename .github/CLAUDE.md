# CLAUDE.md — `.github/`

## Workflows

- `claude-code-review.yaml` — auto-reviews PRs touching `src/`, `tests/`,
  `scripts/`, `mcp/` (excludes markdown). Uses `sonnet` model.
- `claude.yaml` — responds to `@claude` mentions on issues/PRs. Uses `sonnet`
  model.
- `dagster-cloud-deploy.yaml` — reusable workflow (`workflow_call`) for
  multi-arch Docker builds and Dagster Cloud deploys. Called by per-location
  `deploy-prod-*.yaml` workflows.
- `trunk-check.yaml` — runs Trunk linter on PRs (excludes `requirements.txt`).
- `mkdocs-gh-deploy.yaml` — deploys docs site.

## Editing Workflows

- GitHub Actions does not allow both `paths` and `paths-ignore` on the same
  event — use `!` negation patterns instead (e.g., `!**/*.md`).
- YAML values should not be redundantly quoted — Trunk flags it. Only quote when
  required (e.g., `!` negation patterns need quotes).

## Other Files

- `CODEOWNERS` — `@TEAMSchools/admins` owns everything by default;
  `data-engineers` own `src/teamster/`, regional teams own their dbt projects.
- `dependabot.yml` — daily `uv` ecosystem updates.
- `pull_request_template.md` — checklist for PRs (Dagster, dbt, docs sections).
- `actionlint.yaml` — self-hosted runner labels for actionlint.
