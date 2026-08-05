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
| `finalsite` | API + SFTP    | schedule (contacts 04:00 + 12:00 ET) + couchdrop sensor |
| `fldoe`     | SFTP assets   | `AutomationConditionSensor`                             |
| `iready`    | SFTP assets   | sensor (`build_iready_sftp_sensor`)                     |
| `renlearn`  | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)                   |
| `extracts`  | BigQuery→SFTP | schedule (Focus delivery 12:45 ET)                      |
| `couchdrop` | sensor only   | sensor (Google Drive watcher)                           |
| `dlt/focus` | dlt assets    | schedule (04:00, 12:00, 14:45 ET)                       |

## Midday Focus import cycle

The three schedule times above are one chain, not independent cadences. It
exists to keep a promise to stakeholders: a student entered in Finalsite by
12:00pm ET is usable in Focus by 2:00pm ET. Order: ops manually pushes the
Finalsite SFTP export at 12:00 (Finalsite's own export is overnight and not ours
to reschedule) → couchdrop sensor ingests within 10 min → contacts pull and
Focus dlt pull both at 12:00 → dbt rebuild ~3.5 min → four CSVs delivered to the
Focus SFTP `incoming/` folder at 12:45 → **ops runs the Focus imports by hand**
→ dlt pull again at 14:45.

**The three midday inputs run concurrently on purpose.** They share no pool and
none gates another: the contacts API pull and the manually-pushed SFTP drop feed
opposite sides of `int_finalsite__enrollment_lifecycle`, and the dlt pull feeds
the import-once anti-join. Don't re-stagger them looking for an ordering that
isn't there. Top-of-hour GKE Autopilot fan-out can add 3-9 min of step-pod
scheduling wait, which only queues the run — against 45 min before the delivery
that is noise, so these deliberately sit at `12:00` rather than an offset
minute.

Three constraints to preserve when touching any of these times:

- **The 12:45 delivery is a plain cron — nothing gates it on the upstreams.**
  The gaps are a time budget, not a dependency. Measured need is 4-7 min from a
  schedule firing to the dependent staging table being rebuilt, or ~16 min worst
  case from a manual SFTP push (10 min sensor poll + 2 min ingest + 3.5 min dbt)
  plus up to 9 min of top-of-hour pod-scheduling queue, against 45 min of
  budget. Spending that margin ships a delivery built on incomplete inputs with
  no error raised anywhere.
- **`rpt_focus__*` import-once is an anti-join against the dlt SNAPSHOT of
  Focus, not live Focus.** A snapshot older than the last hand-run Focus import
  makes the next delivery re-send those records and duplicate them. Three
  snapshots a day means any one of them prevents that: 14:45 catches the
  same-day imports, 04:00 is the overnight backstop, and 12:00 is the last line
  of defence if both failed. Don't reason about any one of them alone.
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
