# Dagster

## Tableau Workbooks

### How to manage Tableau refresh schedules

Our Tableau workbook assets are defined according to the configurations contained in
`src/teamster/code_locations/kipptaf/tableau/config/assets.yaml`.

**To create or update a refresh schedule:**

Add or edit the value of `assets[*].metadata.cron_schedule` with a valid **cron** string. It can be
either a string (for a single schedule tick) or a list of strings (for multiple).

!!! tip

    Use [crontab guru](https://crontab.guru/) as a cron reference.

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

To "turn off" a schedule, simply comment out the `cron_schedule` attribute:

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
