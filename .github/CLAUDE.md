# CLAUDE.md — `.github/`

## Workflows

- `claude-code-review.yaml` — auto-reviews PRs touching `src/`, `tests/`,
  `scripts/`, `.github/workflows/`. Gating, the headless-deadlock caveat,
  branch-deployment and push-`paths` behavior: `pr-ci-review` skill.
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
- Long quoted CLI args in `claude_args` belong in a folded block scalar (`>-`) —
  prettier reflows the value, and folding turns each inserted newline back into
  a single space, so the resolved string survives formatting unchanged. Verify
  by parsing the YAML AFTER the fmt hook runs, not before.
- Every external action `uses:` is pinned to a full 40-char commit SHA with a
  trailing `# vX.Y.Z` comment (Dependabot's `github-actions` ecosystem proposes
  bumps). Local reusable-workflow refs (`./.github/workflows/*.yaml`) are not
  SHA-pinnable. Keep `actions/checkout` on one version across workflows.
- Dagster Cloud actions are pinned to a commit SHA (all `uses:` point at the
  same tag) — update all occurrences together when upgrading.
- All workflows gate on `github.actor != 'dependabot[bot]'` — maintain this when
  adding new workflows. **One deliberate exception:** `pytest.yaml` omits the
  gate, because its `paths` include `pyproject.toml` and `uv.lock` and
  dependabot is the actor that changes them — gating it would mean the launch
  page's tests never run on the PRs most likely to break them. Do not "restore
  consistency" there without reading the comment in that file first.
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
| `analytics-engineers` | maintain  | `src/dbt/`, `src/cube/`, `docs/launch/`                                       |
| `analysts`            | write     | kipptaf folders without staging models (see CODEOWNERS)                       |
| `data-team`           | write     | docs                                                                          |

- GitHub API uses `push` (not `write`) for the permission field when setting
  team repo access.

## Other Files

- `pull_request_template.md` — checklist for PRs (Dagster, dbt, docs sections).
  Three tiers, plain to detailed: "Summary & Motivation" is plain-language, what
  and why. "Reviewer Notes" is also plain-language — name what's worth a second
  look and why, a line or two each, not the full reasoning. The "For Claude"
  fold-out at the end holds the full technical detail behind each Reviewer Notes
  flag (exact values, edge cases, full reasoning), plus whatever else got
  simplified or cut from Summary for plain-language readability, AI-involvement
  notes, and anything a future `@claude` invocation needs.
- `ISSUE_TEMPLATE/` — `bug_report.md` and `feature_request.md`, each with a "For
  Claude" section for `@claude`-driven issues; `config.yml` disables blank
  issues.
- `actionlint.yaml` — self-hosted runner labels for actionlint.
