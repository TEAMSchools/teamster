# CLAUDE.md — `teamster/code_locations/kippmiami/`

## Identity

```python
CODE_LOCATION = "kippmiami"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippmiami`

## Active Integrations

| Module      | Type          | Trigger                                                                |
| ----------- | ------------- | ---------------------------------------------------------------------- |
| `dbt`       | dbt assets    | `AutomationConditionSensor`                                            |
| `deanslist` | API assets    | schedule (nightly)                                                     |
| `finalsite` | API + SFTP    | schedule (contacts 04:00 + 12:00 ET) + couchdrop sensor                |
| `fldoe`     | SFTP assets   | `AutomationConditionSensor`                                            |
| `iready`    | SFTP assets   | sensor (`build_iready_sftp_sensor`)                                    |
| `renlearn`  | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)                                  |
| `extracts`  | BigQuery→SFTP | schedules (Focus delivery 13:15 ET staffed, 03:45 ET overnight)        |
| `couchdrop` | sensor only   | sensor (Google Drive watcher)                                          |
| `dlt/focus` | dlt assets    | schedule (04:00 ET, count-only tables only) + intraday sensor (15 min) |

## Midday Focus import cycle

This exists to keep a promise to stakeholders: a student entered in Finalsite by
12:00pm ET is usable in Focus by 2:00pm ET. Order: ops manually pushes the
Finalsite SFTP export at 12:00 (Finalsite's own export is overnight and not ours
to reschedule) → couchdrop sensor ingests within 5 min → contacts pull at 12:00
→ dbt rebuild ~3.5 min → four CSVs delivered to the Focus SFTP `incoming/`
folder at 13:15 → **ops runs the Focus imports by hand**. Focus's own live-data
freshness is no longer tied to that 12:00 slot — see below.

A second, unstaffed delivery runs at 03:45 so the overnight Finalsite state is
already staged when ops start their shift. It is not load-bearing for the 2pm
commitment, and its clock time is not tied to the 04:00 dlt tier — see
`extracts/schedules.py`.

**The 12:00 contacts pull and the manually-pushed SFTP drop run concurrently on
purpose.** They share no pool and neither gates the other: the contacts API pull
and the manually-pushed SFTP drop feed opposite sides of
`int_finalsite__enrollment_lifecycle`. Don't re-stagger them looking for an
ordering that isn't there. Top-of-hour GKE Autopilot fan-out can add 3-9 min of
step-pod scheduling wait, which only queues the run — against 45 min before the
delivery that is noise, so this deliberately sits at `12:00` rather than an
offset minute.

Constraints to preserve when touching any of these:

- **The 13:15 delivery is a plain cron — nothing gates it on the upstreams.**
  The gaps are a time budget, not a dependency. Measured need is 4-7 min from a
  schedule firing to the dependent staging table being rebuilt, or ~11 min worst
  case from a manual SFTP push (5 min sensor poll + 2m13s ingest + 3m34s dbt)
  plus up to 9 min of top-of-hour pod-scheduling queue, against 75 min of
  budget. That 5-minute poll is deliberate and Miami-only — see
  `couchdrop/sensors.py`; at the 10 min the other locations use, the ~16 min
  worst case leaves the 12:30 freshness check on #4736 unable to tell a stalled
  chain from one still in flight. Spending this margin ships a delivery built on
  incomplete inputs with no error raised anywhere.
- **`rpt_focus__*` import-once is an anti-join against the dlt SNAPSHOT of
  Focus, not live Focus.** A snapshot older than the last hand-run Focus import
  makes the next delivery re-send those records and duplicate them. The
  `kippmiami__dlt__focus__intraday_sensor` probes every Focus table every 15
  minutes and loads only what changed, so that snapshot is now refreshed within
  ~15 minutes of any change instead of at fixed clock times — this makes the
  dependency **easier** to satisfy than the old three-cron setup, not harder.
  The `0 4 * * *` schedule is the unconditional overnight backstop for only the
  count-only tables (`cursor_column: null` in `config/focus.yaml` —
  `co_teachers` and `login_history` as of writing), which is the set the
  sensor's count-only probe can't fully see an in-place edit on. The other 75
  `updated_at`-tracked tables have NO unconditional reload anymore — if one of
  them is ever suspected of drifting (a stuck signature, a bad cursor), fix it
  with a manual launch of the Focus asset job for that table, not by waiting for
  a nightly pass that no longer touches it. The safe rule for ops is unchanged
  and was never a clock time: do not re-run the delivery unless a Focus sync has
  run SINCE the last import.
- **First diagnostic when midday Focus data looks stale: check whether the
  intraday sensor is running.** It ships with `defaultStatus` STOPPED and must
  be enabled by hand after a one-off manual load of all 77 tables has seeded
  their baselines — the 04:00 tier cannot seed them, since it now targets only
  the count-only tables (see `libraries/dlt/focus/CLAUDE.md`). A stopped sensor
  now silently freezes every `updated_at`-tracked table — the 04:00 tier no
  longer reloads them as a daily fallback, only the two count-only tables — so
  this is the first thing to check, where "did the 12:00 cron fire?" used to be.
- **Keep the 04:00 runs**, but note what they cover changed: the tier now
  reloads only the count-only tables (`co_teachers`, `login_history`), not a
  full refresh. FRESH's Miami enrollment/attendance rows and the rest of
  Focus-sourced Miami data come from `updated_at`-tracked tables the intraday
  sensor keeps fresh continuously — losing the 04:00 tier would not put those on
  day-old data. It would delay picking up an in-place edit to a count-only table
  by up to a day.

`kippmiami__extracts__focus__asset_job_schedule` also has to be STARTED in the
Dagster+ UI; its `defaultStatus` is STOPPED and it had never run in prod as of
#4736.

The `dlt_focus_kippmiami` pool must stay at limit 1 (Dagster+ deployment
setting) — the 04:00 schedule is a plain cron with no in-flight guard of its own
(only the intraday sensor calls `in_flight_run`), so the pool limit is the only
thing preventing that schedule run and a sensor run from overlapping and racing
on the shared `_dlt_pipeline_state` row. Confirm the limit before enabling the
sensor.

## Florida-Specific

Miami is the only code location with `fldoe` (Florida Department of Education
assessment data — FSA, EOC, Science). These are SFTP assets from a Florida state
data file drop.

PowerSchool (pre-Focus SIS) is retired — frozen archive in BigQuery dataset
`kippmiami_powerschool`; do not drop.
