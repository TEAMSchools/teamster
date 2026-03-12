# Pull Request

## Summary & Motivation

[//]: # "When merged, this pull request will..."

## Self-review

### General

- [ ] If this is a same-day request, please flag that in the #data-team Slack
- [ ] Update **due date** and **assignee** on the
      [TEAMster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838)
- [ ] Run `trunk check` and `trunk fmt` on all modified files

### Dagster

- [ ] Run `uv run dagster definitions validate` for any modified code location
- [ ] New integrations follow the
      [Library + Config pattern](https://teamschools.github.io/teamster/reference/adding-an-integration/)
      with the correct asset key format and IO manager

### dbt

- [ ] Include a `[model_name].yml` properties file for all new models — see
      [dbt Conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/#model-properties-file)
- [ ] Include (or update) an
      [exposure](https://teamschools.github.io/teamster/reference/dbt-conventions/#exposures)
      for all models consumed by a dashboard, analysis, or application
- [ ] SQL follows
      [dbt SQL conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/#sql-conventions)
- [ ] If adding a new external source, run `stage_external_sources` before
      building — see
      [SQL conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/#sql-conventions)

### CI checks

- [ ] **Trunk** — passes. If it fails, run `trunk check` and `trunk fmt`
      locally, fix any issues, and push again.
- [ ] **dbt Cloud** — passes. If it fails: click **Details** on the check →
      expand **Invoke `dbt build ...`** → **Debug Logs**.
- [ ] **Dagster Cloud** — passes or not triggered (only runs when relevant paths
      change and the PR is not a draft). If it fails: check the **Actions** tab
      for the workflow run logs. Re-run failed jobs if the failure looks
      transient; otherwise check the **Dagster Cloud** branch deployment for
      error details.
- [ ] **Claude Code Review** — review the automated comment. Note: Claude is not
      a blocking check and its feedback may contain errors; use your judgement.

## Troubleshooting

- [SqlFluff Rules Reference](https://docs.sqlfluff.com/en/stable/rules.html)
- [Dagster "kinds" Reference](https://docs.dagster.io/guides/build/assets/metadata-and-tags/kind-tags#supported-icons)
- [Automated checks](https://teamschools.github.io/teamster/CONTRIBUTING/#automated-checks)
- [dbt Conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/)
