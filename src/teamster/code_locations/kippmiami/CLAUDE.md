# CLAUDE.md — `teamster/code_locations/kippmiami/`

## Identity

```python
CODE_LOCATION = "kippmiami"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

## Active Integrations

| Module      | Type          | Trigger                                                                |
| ----------- | ------------- | ---------------------------------------------------------------------- |
| `dbt`       | dbt assets    | `AutomationConditionSensor`                                            |
| `finalsite` | API + SFTP    | schedule (contacts 00:15 + 12:00 ET) + couchdrop sensor                |
| `fldoe`     | SFTP assets   | `AutomationConditionSensor`                                            |
| `iready`    | SFTP assets   | sensor (`build_iready_sftp_sensor`)                                    |
| `renlearn`  | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)                                  |
| `extracts`  | BigQuery→SFTP | schedule (Focus delivery 13:15 ET staffed + 03:45 ET overnight)        |
| `couchdrop` | sensor only   | sensor (Google Drive watcher)                                          |
| `dlt/focus` | dlt assets    | schedule (04:00 ET, count-only tables only) + intraday sensor (15 min) |

## Midday Focus import cycle

This exists to keep a promise to stakeholders: a student entered in Finalsite by
12:00pm ET is usable in Focus by 2:00pm ET. Order: ops manually pushes the
Finalsite SFTP export at 12:00 (Finalsite's own export is overnight and not ours
to reschedule) → couchdrop sensor ingests within 5 min → contacts pull at 12:00
→ dbt rebuild ~3.5 min → four CSVs delivered to the Focus SFTP `incoming/`
folder at 13:15 → **ops runs the Focus imports by hand**. Focus's own live-data
freshness runs on its own schedule — see below.

A second, unstaffed delivery runs at 03:45 so the overnight Finalsite state is
already staged when ops start their shift. It is not load-bearing for the 2pm
commitment, and its clock time is not tied to the 04:00 dlt tier — see
`extracts/schedules.py`. Both deliveries are crons on the SAME
`ScheduleDefinition`, so enabling that one schedule enables both.

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
  The gap is a time budget, not a dependency. Keep Miami's 5-min couchdrop poll
  (`couchdrop/sensors.py`) and do not shrink the 12:00-to-13:15 margin: a
  delivery built on incomplete inputs raises no error.
- **`rpt_focus__*` import-once is an anti-join against the dlt SNAPSHOT of
  Focus, not live Focus.** A snapshot older than the last hand-run Focus import
  makes the next delivery re-send those records and duplicate them. The
  `kippmiami__dlt__focus__intraday_sensor` probes every Focus table every 15
  minutes and loads only what changed, so that snapshot is refreshed within ~15
  minutes of any change. Tiering and the 04:00 count-only reload:
  `libraries/dlt/focus/CLAUDE.md` → _Probe gating_. A suspected drifting
  `updated_at` table (a stuck signature, a bad cursor) gets a manual launch of
  the Focus asset job for that table. The safe rule for ops is not a clock time:
  do not re-run the delivery unless a Focus sync has run SINCE the last import.
- **First diagnostic when midday Focus data looks stale: check whether the
  intraday sensor is running.** It ships with `defaultStatus` STOPPED (enable
  order: focus _Probe gating_). A stopped sensor silently freezes every
  `updated_at`-tracked table.
- **The `contacts` API pull runs at 00:15, not 04:00.** That still lands before
  FRESH's 05:00 Tableau extract, so Miami's morning dashboard reads same-day
  data, and it puts `contacts` ahead of the NJ consumers of
  `stg_finalsite__contacts` at 01:00 (Google Directory user sync) and 01:25
  (DeansList). It is independent of the dlt Focus 04:00 tier above. See #4715.

A freshness alert on `stg_finalsite__contacts` (policy in `freshness.py`, shared
with the other districts) usually means a missing `contacts` partition: backfill
it in the Dagster UI and staging rebuilds on the next automation tick.

`kippmiami__extracts__focus__asset_job_schedule` has `defaultStatus` STOPPED and
must be started in the Dagster+ UI.

The `dlt_focus_kippmiami` pool stays at limit 1: `libraries/dlt/CLAUDE.md` →
_Pool limits_.

## Florida-Specific

Miami is the only code location with `fldoe` (Florida Department of Education
assessment data — FSA, EOC, Science). These are SFTP assets from a Florida state
data file drop.

PowerSchool (pre-Focus SIS) is retired. The `powerschool` module holds dlt
assets that pull Miami's server into `dagster_kippmiami_dlt_powerschool`, the
source of the frozen `kippmiami_powerschool` archive. They are off: the module
is left out of `definitions.py`, and the `db_powerschool` / `ssh_powerschool`
resources and their secrets stay wired so turning it on is the 2-line edit the
comment there describes. Turn it on only to re-pull tables for an archive
rebuild (dbt recipe: `src/dbt/kippmiami/CLAUDE.md`), then off again in the same
PR. While on, the location also carries the dbt `kippmiami/powerschool/*`
assets, and runs are launched by hand with no in-flight guard, so the
`dlt_powerschool_kippmiami` pool limit of 1 (`libraries/dlt/CLAUDE.md`) is the
only thing keeping two launches from racing. kipptaf reads the archive as a
BQ-native source. Do not drop either dataset or the GCS files under
`gs://teamster-kippmiami/dagster/kippmiami/powerschool/`.

`kippmiami_deanslist` is a frozen dataset that kipptaf still unions for history.
Do not drop it or the GCS files under
`gs://teamster-kippmiami/dagster/kippmiami/deanslist/`.
