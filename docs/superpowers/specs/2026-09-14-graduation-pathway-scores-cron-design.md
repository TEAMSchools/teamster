# Rebuild `int_students__graduation_pathway_scores` on its consumer's cron

Issue: [#5310](https://github.com/TEAMSchools/teamster/issues/5310), child of
[#5212](https://github.com/TEAMSchools/teamster/issues/5212).

## Problem

`int_students__graduation_pathway_scores` is a table on the default eager
condition. Its 3 score sources are views, so any data change under them fires a
rebuild. In the 7 days ending 2026-09-14 it rebuilt 994 times and cost 51 slot
hours, 4th in the prod dbt ranking.

Its only consumer, `int_students__graduation_path_codes`, runs on cron
`0 3,16 * * *` (#4821) and rebuilt 15 times in the same week. About 980 of the
994 rebuilds were never read.

## Evidence that nothing needs it fresher

- Repo: one `ref()`, from `int_students__graduation_path_codes`. No Cube view,
  exposure, or Dagster asset reads the scores model.
- Warehouse, 30 days to 2026-09-14: no reader of the prod table other than its
  own tests, dbt Cloud CI rebuilding the `zz_stg` copy, and 8 ad hoc dev
  queries.
- #4821 already mapped the downstream cadence: `kipp_forward_data_suite` at
  04:00 and 17:00, `high_school_early_warning_dashboard` at 06:00. Both are
  served by the 03:00 and 16:00 ticks.

## Design

Add to `config` in
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__graduation_pathway_scores.yml`:

```yaml
meta:
  dagster:
    automation_condition:
      cron_schedule: 0 3,16 * * *
```

Same tick as the consumer, no stagger. The shared `~any_deps_in_progress` guard
in `dbt_cron_automation_condition` builds the scores model first, then the path
codes, per `.claude/rules/dbt-models.md` (View→table flips).

No SQL change. The 70-stage plan and 3 slot minutes per run stay. At 2 runs a
day that is under 1 slot hour a week.

## Rejected

- Cron one hour earlier. The repo rule says same tick; a stagger is a second
  cron to keep in step for no gain.
- Materialize the 3 view upstreams. Cuts per-run cost, but each view has its own
  consumers and cadence questions. Three audits for a node that needs 2 rebuilds
  a day.

## Verification

- `uv run dbt parse` in the worktree succeeds.
- After merge, the new condition takes effect at the next cron tick. A
  properties-only change does not fire `code_version_changed`.
- Done when the 7-day ranking from #5212, over a window that starts after the
  merge, shows the model at or under 2 runs a day and under 2 slot hours.
