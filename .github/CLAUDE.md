# CLAUDE.md — `.github/`

## Workflows

- `claude-code-review.yaml` — auto-reviews PRs touching `src/`, `tests/`,
  `scripts/`, `mcp/` (excludes markdown).
- `claude.yaml` — responds to `@claude` mentions on issues/PRs.
- `dagster-cloud-deploy.yaml` — reusable workflow (`workflow_call`) for
  multi-arch Docker builds and Dagster Cloud deploys. Called by per-location
  `deploy-prod-*.yaml` workflows. Uses `cancel-in-progress: true` grouped by
  workflow + ref + event — rapid pushes to the same branch cancel prior deploys.
  Does not prevent multiple locations deploying simultaneously from one commit.
- `trunk-check.yaml` — runs Trunk linter on PRs (excludes `requirements.txt`).
- `mkdocs-gh-deploy.yaml` — deploys docs site on push to `main`.
- `deploy-cube-mcp.yaml` — builds and deploys the Cube MCP server to Cloud Run
  (`teamster-mcp`) on push to `main` when `src/cube/mcp/**` changes.

## Editing Workflows

- GitHub Actions does not allow both `paths` and `paths-ignore` on the same
  event — use `!` negation patterns instead (e.g., `!**/*.md`).
- YAML values should not be redundantly quoted — Trunk flags it. Only quote when
  required (e.g., `!` negation patterns need quotes).
- All workflows use `actions/checkout@v6` — keep this consistent.
- Dagster Cloud actions are pinned to a specific version tag (not `@latest`) —
  update all occurrences together when upgrading.
- All workflows gate on `github.actor != 'dependabot[bot]'` — maintain this when
  adding new workflows.
- `DAGSTER_CLOUD_API_TOKEN` is scoped to the `prerun` and `deploy` jobs only —
  do not move it to workflow-level `env`.

## Workload Identity Federation

WIF pool lives in `teamster-332318`. The `google-github-actions/auth@v3` step
has no `service_account` field — direct WIF; the deploy identity is the WIF
principal itself.

- Attribute mapping includes `attribute.repository=assertion.repository`. Grants
  target:
  `principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github/attribute.repository/TEAMSchools/teamster`
- Cross-project IAM for Cloud Run deploys: grant `roles/run.admin`,
  `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser` to the
  principalSet on the target project; also bind `serviceAccountUser` on the
  runtime SA.

## Teams and CODEOWNERS

| Team                  | Repo role | CODEOWNERS scope                                                              |
| --------------------- | --------- | ----------------------------------------------------------------------------- |
| `admins`              | admin     | Global fallback (`*`)                                                         |
| `platform`            | maintain  | `.github/`, `.devcontainer/`, `.claude/`, `.trunk/`, Dockerfile, scripts, MCP |
| `data-engineers`      | write     | `src/teamster/`, tests                                                        |
| `analytics-engineers` | maintain  | All `src/dbt/`                                                                |
| `analysts`            | write     | kipptaf folders without staging models (see CODEOWNERS)                       |
| `data-team`           | write     | docs                                                                          |

- GitHub API uses `push` (not `write`) for the permission field when setting
  team repo access.

## Other Files

- `pull_request_template.md` — checklist for PRs (Dagster, dbt, docs sections).
- `actionlint.yaml` — self-hosted runner labels for actionlint.
