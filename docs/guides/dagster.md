# Dagster

!!! warning "DON'T PANIC! :fontawesome-solid-thumbs-up:"

## Tier 1 Troubleshooting

### Asset health

Check the
[Asset Health](https://kipptaf.dagster.cloud/prod/overview/asset-health) page
for failed materializations. If there are any, click on the link to the Asset
Overview and click the "Materialize..." button to force a new run. If the asset
is partitioned, go to the "Partitions" view, filter for "Failed" partitions and
materialize only those partitions.

### Slack alerts

Check [#dagster-alerts](https://kippnj.slack.com/archives/C04A0KC1YSW) on Slack
for failed Job runs. These are rare, but you may see some logs from our nightly
user-provisioning scripts. Typically, they indicate an issue on the vendor side
or something that will require a manual intervention (e.g. a rehire uses their
work email as their personal email on ADP) or a code change. Log them on Asana.

## dbt external sources

When `build_dbt_assets()` runs, it automatically stages any external sources
upstream of the selected assets before executing `dbt build`. This means:

- **No Dagster code changes are needed when adding a new external source.** Add
  the source to your dbt project's YAML and it will be staged automatically on
  the next run.
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
  Dagster will create a schedule and manage the refresh.
- **Tableau Server (or another system) owns it** → omit `cron_schedule`. The
  workbook still appears in the Dagster asset graph (via the `id` metadata) but
  its refresh is not managed by Dagster.

Do not set `cron_schedule` for workbooks that are already scheduled in Tableau
Server — this would cause double-refreshes.

### How to manage Tableau refresh schedules

Our Tableau workbook assets are defined according to the configurations
contained in `src/teamster/code_locations/kipptaf/tableau/config/assets.yaml`.

**To create or update a refresh schedule:**

Add or edit the value of `assets[*].metadata.cron_schedule` with a valid
**cron** string. It can be either a string (for a single schedule tick) or a
list of strings (for multiple).

!!! tip

    Use [crontab guru](https://crontab.guru/) as a cron reference.

<!-- prettier-ignore-start -->
<!-- trunk-ignore(markdownlint/MD046) -->
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
<!-- prettier-ignore-end -->

To "turn off" a schedule, simply comment out the `cron_schedule` attribute:

<!-- prettier-ignore-start -->
<!-- trunk-ignore(markdownlint/MD046) -->
```yaml
- name: My Tableau Workbook
  deps:
    - [spam, eggs, jeff]
  metadata:
    id: 0n371m37-h34c-702w-h0p1-4y3dm2831v3d
    # cron_schedule: 0 2 * * *
- name: My Other Tableau Workbook
  deps:
    - [foo, bar, baz]
  metadata:
    id: 3235470n-h158-4115-4nd7-h3yh4d705hu7
    # cron_schedule:
    #   - 0 0 * * *
    #   - 0 12 * * *
```
<!-- prettier-ignore-end -->
