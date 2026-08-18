# CLAUDE.md — `.github/`

## Workflows

- `claude-code-review.yaml` — auto-reviews PRs touching `src/`, `tests/`,
  `scripts/`, `.github/workflows/` (excludes markdown). A PR editing a workflow
  runs that PR's own copy of it, so workflow changes review themselves. **Gated
  to `base=main` (`branches: [main]`)** — a **stacked PR** (base = another
  feature branch) gets no auto-review. dbt Cloud CI is NOT base-gated: it
  triggers via dbt Cloud's own GitHub app on PR events, independent of any
  GH-Actions `branches` filter, so a stacked PR **does** run dbt Cloud CI
  (verified on #4381) alongside Trunk + Dagster deploy — only
  `claude-code-review` is skipped. Review a stacked PR via
  `superpowers:requesting-code-review` or an `@claude` PR comment (`claude.yaml`
  is comment-triggered, not base-gated). A base-retarget after the parent merges
  does NOT re-fire `opened`, so `claude-code-review` does not auto-trigger then.
- `claude.yaml` — responds to `@claude` mentions on issues/PRs.
- **`claude-code-action` headless deadlock**: the action breaks its SDK loop on
  the FIRST result (`base-action/src/run-claude-sdk.ts`), so a run that
  dispatches background subagents ends with them orphaned and reports `success`
  having posted nothing (upstream #1462 / #1499, unfixed at v1.0.183; ~8-12% of
  fan-out runs). `Agent`, `Workflow`, `ScheduleWakeup`, `SendMessage` and
  `Monitor` are NOT gated by `--allowedTools` — deny them via
  `--disallowedTools` in `claude_args`. A second `--allowedTools` /
  `--disallowedTools` ACCUMULATES with the action's own list rather than
  replacing it (`parse-sdk-options.ts` `ACCUMULATING_FLAGS`), so adding tools
  cannot strip `update_claude_comment`.
- **Debugging a silent `claude-review`**: `display_report: true` appends the
  transcript — final assistant message, denied tool calls — to the run's **job
  summary**, the only place they appear. Not in the REST API, and not in the
  step log (`show_full_output`-gated). Read it before theorising.
- **Which ref a workflow runs from**: `pull_request` runs the PR's OWN copy, so
  a workflow change tests itself on that PR. `issue_comment` (`claude.yaml`)
  runs the DEFAULT-branch copy — an `@claude` mention cannot exercise an
  unmerged `claude.yaml`; probe such a change through a `pull_request` workflow
  instead.
- `dagster-cloud-deploy.yaml` — reusable workflow (`workflow_call`) for
  multi-arch Docker builds and Dagster Cloud deploys. Called by per-location
  `deploy-prod-*.yaml` workflows. Uses `cancel-in-progress: true` grouped by
  workflow + ref + event — rapid pushes to the same branch cancel prior deploys.
  Does not prevent multiple locations deploying simultaneously from one commit.
- **Branch deployments build only on a NON-draft PR** —
  `deploy-prod-<location>.yaml` gates the deploy job
  `if: ${{ !github.event.pull_request.draft }}`. To get a branch deployment
  (e.g. to test a change before merge), open the PR ready-for-review, not draft.
  A change to a shared `pull_request`-path file (`uv.lock`, `Dockerfile`,
  `src/teamster/core/**`) fans a branch-deploy build out to ALL five locations,
  not just the one you touched — including when that shared change arrives via a
  `main`-merge commit on the branch: the `pull_request`/`synchronize` `paths`
  filter matches the pushed delta (which includes the merge commit), NOT the net
  three-dot PR diff (where the merged-in files, now equal to main, don't
  appear).
- **A markdown-only commit still re-triggered the `kipptaf` deploy** on
  `pull_request`, despite `"!**/CLAUDE.md"` in BOTH trigger blocks of
  `deploy-prod-kipptaf.yaml` (verified: the commit touched 3 files, all `.md`,
  and a `kipptaf` run appeared for that headSha). This contradicts the
  pushed-delta model above, which predicts no run — one of the two is
  incomplete, and no mechanism is established here. Plan for the cost: a
  docs-only push to a PR is NOT free, so batch doc changes into the code commit
  rather than splitting them off to "avoid CI".
- **Each `deploy-prod-<location>.yaml` push-`paths` must list every dbt package
  in that district's `src/dbt/<district>/packages.yml`** (`src/dbt/pearson/**`,
  etc.). Drift silently skips that district's prod deploy on a shared
  source-package change, stranding it on stale code (PR #4175: paterson omitted
  `src/dbt/pearson/**` → failed contract enforcement while newark/camden
  deployed). After merging a source-package change, confirm every consuming
  district deployed (`gh run list --branch main`); a post-merge prod failure
  whose run tags show the OLD `dagster/git_commit_hash`/image is a
  missed/lagging deploy, not a code bug. The `pull_request` `paths`
  intentionally exclude `src/dbt/**` (dbt Cloud CI covers those); only the
  `push` section needs them.
- **The same push-`paths` drift hits shared Dagster library code**, not just dbt
  packages: `deploy-prod-<location>.yaml` must list every
  `src/teamster/libraries/<lib>/**` the location imports. A shared-library
  change (e.g. the Focus dlt fix #4216) silently skipped the kippmiami deploy
  because `src/teamster/libraries/dlt/**` was missing — only kipptaf, which
  listed it, deployed (fixed #4219). After merging a library change, confirm the
  consuming location actually **reloaded** before acting on the new code:
  `mcp__dagster__get_location_load_history` → newest entry `loadStatus: LOADED`
  with a matching `commit_hash`. A green Actions deploy job ≠ agent reloaded,
  and a missing push-path means it never deployed at all.
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
| `analytics-engineers` | maintain  | `src/dbt/`, `src/cube/`, `src/launch/`                                        |
| `analysts`            | write     | kipptaf folders without staging models (see CODEOWNERS)                       |
| `data-team`           | write     | docs                                                                          |

- GitHub API uses `push` (not `write`) for the permission field when setting
  team repo access.

## Other Files

- `pull_request_template.md` — checklist for PRs (Dagster, dbt, docs sections).
  Keep "Summary & Motivation" plain-language; put tradeoffs, edge cases, and
  verification detail in the visible "Reviewer Notes" section instead — that
  content is for every reviewer, not just Claude. The "For Claude" fold-out at
  the end is narrower: AI-involvement notes and anything a future `@claude`
  invocation needs, nothing a human reviewer needs to see.
- `ISSUE_TEMPLATE/` — `bug_report.md` and `feature_request.md`, each with a "For
  Claude" section for `@claude`-driven issues; `config.yml` disables blank
  issues.
- `actionlint.yaml` — self-hosted runner labels for actionlint.
