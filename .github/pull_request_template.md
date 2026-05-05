# Pull Request

## Summary & Motivation

> "When merged, this pull request will..."

## AI Assistance

> If Claude Code authored or co-authored this PR, briefly note what was
> AI-assisted vs. human-directed in the summary above

## Self-review

> Complete only the sections relevant to your changes.

### General

> If this is a same-day request, please flag that in the #data-team Slack

- [ ] Update **due date** and **assignee** on the
      [TEAMster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838)
- [ ] Review the **Claude Code Review** comment posted on this PR. Address valid
      feedback; dismiss false positives with a brief reply explaining why.
      (Claude is advisory — use your judgement, but don't ignore it.)

### Dagster _(skip if no Dagster changes)_

- [ ] Run `uv run dagster definitions validate` for any modified code location
- [ ] Run `uv run pytest tests/test_dagster_definitions.py` for any modified
      code location
- [ ] New integrations follow the
      [Library + Config pattern](https://teamschools.github.io/teamster/reference/adding-an-integration/)
      with the correct asset key format and IO manager

### dbt _(skip if no dbt changes)_

- [ ] Include a `[model_name].yml` properties file for all new models — see
      [dbt Conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/#model-properties-file)
- [ ] Include (or update) an
      [exposure](https://teamschools.github.io/teamster/reference/dbt-conventions/#exposures)
      for all models consumed by a dashboard, analysis, or application
- [ ] **Breaking change?** Renaming or removing columns in a contracted model
      (`stg_`, `rpt_`, mart) will break downstream exposures. Coordinate with
      affected teams before merging and document your rollback plan in the
      summary above.
- [ ] If adding or modifying an external source, run `stage_external_sources`
      with **`--target staging`** so the dbt Cloud CI job can find the table.
      See
      [Staging external sources](https://teamschools.github.io/teamster/guides/dbt-development/#staging-external-sources)

### Docs _(skip if no schedule, sensor, or integration changes)_

- [ ] If adding or changing a schedule or sensor, regenerate the automations
      catalog: `uv run scripts/gen-automations-doc.py`
- [ ] If adding a new integration to a code location, update that location's
      `CLAUDE.md` by running `/claude-md-management:revise-claude-md`

## CI checks

- [ ] **Trunk** — passes. If it fails, run `trunk check` and `trunk fmt`
      locally, fix any issues, and push again.
- [ ] **dbt Cloud** — passes. If it fails: click **Details** on the check →
      expand **Invoke `dbt build ...`** → **Debug Logs**. Or tag **Claude** on
      the PR with the error details.
- [ ] **Dagster Cloud** — passes or not triggered (only runs when relevant paths
      change and the PR is not a draft). If it fails: check the **Actions** tab
      for the workflow run logs. Re-run failed jobs if the failure looks
      transient; otherwise check the **Dagster Cloud** branch deployment for
      error details. Or tag **Claude** on the PR for help.

## Troubleshooting

- [SqlFluff Rules Reference](https://docs.sqlfluff.com/en/stable/rules.html)
- [Dagster "kinds" Reference](https://docs.dagster.io/guides/build/assets/metadata-and-tags/kind-tags#supported-icons)
- [Automated checks](https://teamschools.github.io/teamster/CONTRIBUTING/#automated-checks)
- [dbt Conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/)
