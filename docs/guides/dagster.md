# Dagster

## dbt external sources

When `build_dbt_assets()` runs, it automatically stages any external sources
upstream of the selected assets before executing `dbt build`:

- **No Dagster code changes are needed when adding a new external source.** Add
  the source to your dbt project's YAML and it will be staged on the next run.
- For external sources using a BigLake `connection_name`, the metadata cache is
  also refreshed automatically.

To stage sources manually (e.g. after adding a new one locally):

```bash
uv run dbt run-operation stage_external_sources \
  --vars "{'ext_full_refresh': 'true'}" \
  --args 'select: [model_name]'
```

## Tableau Workbooks

### Ownership: Dagster-scheduled vs externally-scheduled

Before adding a `cron_schedule` to a Tableau workbook exposure, decide whether
**Dagster owns the refresh trigger**:

- **Dagster owns it** → add `cron_schedule` to the exposure's `asset.metadata`.
  Dagster creates a schedule and manages the refresh.
- **Tableau Server owns it** → omit `cron_schedule`. The workbook still appears
  in the asset graph (via the `id` metadata) but its refresh is not managed by
  Dagster.

Do not set `cron_schedule` for workbooks already scheduled in Tableau Server —
this causes double-refreshes.

### Managing refresh schedules

Tableau workbook assets are configured in
`src/teamster/code_locations/kipptaf/tableau/config/assets.yaml`.

Set `assets[*].metadata.cron_schedule` to a cron string (single schedule) or a
list of strings (multiple ticks). Use [crontab guru](https://crontab.guru/) as a
reference.

```yaml
- name: My Tableau Workbook
  deps:
    - [spam, eggs, jeff]
  metadata:
    id: 0n371m37-h34c-702w-h0p1-4y3dm2831v3d
    cron_schedule: 0 2 * * *
- name: My Other Tableau Workbook
  deps:
    - [foo, bar, baz]
  metadata:
    id: 3235470n-h158-4115-4nd7-h3yh4d705hu7
    cron_schedule:
      - 0 0 * * *
      - 0 12 * * *
```

To disable a schedule, comment out the `cron_schedule` key:

```yaml
- name: My Tableau Workbook
  metadata:
    id: 0n371m37-h34c-702w-h0p1-4y3dm2831v3d
    # cron_schedule: 0 2 * * *
```
