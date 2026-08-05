# CLAUDE.md — `teamster/code_locations/kippmiami/`

## Identity

```python
CODE_LOCATION = "kippmiami"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippmiami`

## Active Integrations

| Module      | Type          | Trigger                                                 |
| ----------- | ------------- | ------------------------------------------------------- |
| `dbt`       | dbt assets    | `AutomationConditionSensor`                             |
| `deanslist` | API assets    | schedule (nightly)                                      |
| `finalsite` | API + SFTP    | schedule (contacts 04:00 + 12:10 ET) + couchdrop sensor |
| `fldoe`     | SFTP assets   | `AutomationConditionSensor`                             |
| `iready`    | SFTP assets   | sensor (`build_iready_sftp_sensor`)                     |
| `renlearn`  | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)                   |
| `extracts`  | BigQuery→SFTP | schedule (Focus delivery 12:45 ET)                      |
| `couchdrop` | sensor only   | sensor (Google Drive watcher)                           |
| `dlt/focus` | dlt assets    | schedule (04:00, 12:25, 14:45 ET)                       |

## Midday Focus import cycle

The three schedule times above are one chain, not independent cadences. It
exists to keep a promise to stakeholders: a student entered in Finalsite by
12:00pm ET is usable in Focus by 2:00pm ET. Order: ops manually pushes the
Finalsite SFTP export at 12:00 (Finalsite's own export is overnight and not ours
to reschedule) → couchdrop sensor ingests within 10 min → contacts pull 12:10 →
Focus dlt pull 12:25 → dbt rebuild ~3.5 min → four CSVs delivered to the Focus
SFTP `incoming/` folder at 12:45 → **ops runs the Focus imports by hand** → dlt
pull again at 14:45.

Two constraints to preserve when touching any of these times:

- **`rpt_focus__*` import-once is an anti-join against the dlt SNAPSHOT of
  Focus, not live Focus.** The 14:45 pull is what makes a post-import re-run of
  the delivery safe; drop it and a second same-day delivery duplicates every
  record in Focus.
- **Keep the 04:00 runs.** Miami is Focus-sourced network-wide, and FRESH's
  Tableau extract refreshes at 05:00 — moving the only pull to midday leaves
  every morning dashboard on day-old Miami data.

`kippmiami__extracts__focus__asset_job_schedule` also has to be STARTED in the
Dagster+ UI; its `defaultStatus` is STOPPED and it had never run in prod as of
#4736.

## Florida-Specific

Miami is the only code location with `fldoe` (Florida Department of Education
assessment data — FSA, EOC, Science). These are SFTP assets from a Florida state
data file drop.

PowerSchool (pre-Focus SIS) is retired — frozen archive in BigQuery dataset
`kippmiami_powerschool`; do not drop.
