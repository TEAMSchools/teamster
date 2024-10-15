# Dagster

## Tier 1 Troubleshooting

### Morning routine

1. Check the [Asset Health](https://kipptaf.dagster.cloud/prod/overview/asset-health) page for
   failed materializations. If there are any, click on the link to the Asset Overview and click the
   "Materialize..." button to force a new run. If the asset is partitioned, go to the "Partitions"
   view, filter for "Failed" partitions and materialize only those partitions.

2. Check [#dagster-alerts](https://kippnj.slack.com/archives/C04A0KC1YSW) on Slack for failed Job
   runs. These are rare, but you may see some logs from our nightly user-provisioning scripts.
   Typically, they indicate an issue on the vendor side or something that will require a manual
   intervention (e.g. a rehire uses their work email as their personal email on ADP) or a code
   change. Log them on Asana.

## Tableau Workbooks

### How to manage Tableau refresh schedules

Our Tableau workbook assets are defined according to the configurations contained in
`src/teamster/code_locations/kipptaf/tableau/config/assets.yaml`.

**To create or update a refresh schedule:**

Add or edit the value of `assets[*].metadata.cron_schedule` with a valid **cron** string. It can be
either a string (for a single schedule tick) or a list of strings (for multiple).

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
