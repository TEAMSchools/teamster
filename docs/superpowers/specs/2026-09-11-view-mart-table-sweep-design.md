# View mart table sweep

Materialize the 10 costliest view marts as cron tables so their data tests stop
recomputing the view.

Issue: [#5217](https://github.com/TEAMSchools/teamster/issues/5217). Parent:
[#5212](https://github.com/TEAMSchools/teamster/issues/5212).

## Problem

Marts inherit `materialized: view` from `dbt_project.yml`. BigQuery computes a
view on every read, so every `unique`, `not_null`, and `relationships` test on a
view mart recomputes that entire view before it can check anything.

10 marts cost 936 slot hours a week this way. Total warehouse compute in the
project is 2,912 slot hours a week, of which dbt data tests are 1,387. These 10
marts are 67% of all test compute and 32% of all compute.

Measured over 7 days from `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`. `prod`
is the Dagster agent, `CI` is dbt Cloud on `target: staging`.

| #   | View mart                      | prod |    CI | total |
| --- | ------------------------------ | ---: | ----: | ----: |
| 1   | `bridge_survey_expectations`   | 12.4 | 281.0 | 293.7 |
| 2   | `fct_survey_submissions`       | 23.2 | 215.3 | 238.6 |
| 3   | `fct_student_attendance_daily` |  1.7 |  90.5 | 114.8 |
| 4   | `fct_survey_responses`         |  0.0 | 105.8 | 105.8 |
| 5   | `dim_college_enrollments`      | 13.4 |  27.0 |  40.5 |
| 6   | `dim_survey_administrations`   |  0.0 |  37.9 |  38.3 |
| 7   | `fct_grades_assignments`       |  0.0 |  37.7 |  37.9 |
| 8   | `fct_support_tickets`          | 11.6 |  23.0 |  34.6 |
| 9   | `dim_staff_reporting_chain`    | 22.3 |   0.0 |  22.3 |
| 10  | `dim_staff_work_history`       |  9.6 |   0.0 |   9.6 |

The other 57 view marts cost at most 6.1 slot hours a week each, about 30
combined. The cliff after rank 10 is clean, so the batch stops there.

## Root cause

Two mechanisms drive the two columns. They are independent.

### CI: `state:modified+` selects these marts on nearly every pull request

dbt Cloud CI runs `dbt build --select state:modified+ --full-refresh`. These
marts sit downstream of hub models that most pull requests touch, so CI creates
the view (free) and then runs every attached test against it. For
`bridge_survey_expectations` that is 8 tests at up to 43 slot minutes each, on
114 CI runs a week.

CI is 818 of the 936 hours. prod is 94. The remaining 24 are `dev` and `defer`
targets and rounding.

### prod: eager indirect selection fires child tests on parent rebuilds

In prod these child views are never rebuilt at all, yet their tests still run.

| prod node                                                       | runs in 7 days |
| --------------------------------------------------------------- | -------------: |
| `model.kipptaf.dim_staff`                                       |            192 |
| `model.kipptaf.bridge_survey_expectations`                      |              0 |
| `model.kipptaf.dim_staff_reporting_chain`                       |              0 |
| `test ... bridge_survey_expectations_staff_key__ref_dim_staff_` |            128 |
| `test ... dim_staff_reporting_chain_manager_staff_key__ref_...` |            128 |
| `test unique_dim_staff_staff_key`                               |            128 |

dbt's default `--indirect-selection=eager` selects a test when **any** parent is
selected, per `dbt/graph/selector.py::expand_selection`. A `relationships` test
depends on both the child model and the FK target. `dim_staff` is a table with
the eager automation condition, so it rebuilds 192 times a week, and each
rebuild drags in all of its children's FK tests. Each of those recomputes an
entire child view to check a few thousand keys.

Across all prod dbt tests, 72.3 of 117.5 weekly slot hours (62%) run on models
that never rebuilt in prod during the window.

## Decision

Materialize the 10 marts as tables on a cron automation condition. Do not change
`--indirect-selection`.

Once a mart is a table, both mechanisms become cheap at once: CI builds the
table once instead of recomputing it per test, and a parent-triggered child test
reads a table. One change fixes both columns.

## Design

Each of the 10 properties yml files gains:

```yaml
config:
  materialized: table
  meta:
    dagster:
      automation_condition:
        cron_schedule: "<per-model, see below>"
```

`dbt_table_automation_condition()` is eager on ancestor updates, which would
rebuild these on every upstream data refresh. `dbt_cron_automation_condition()`
swaps that trigger for a cron tick, and per
`src/teamster/libraries/dbt/dagster_dbt_translator.py` it is available only to
TABLE models. So the materialization change is a prerequisite for the cadence
change, not an independent choice.

### Cadence, derived per model

Build cost is estimated from p90 slot minutes per test on that view. The
heaviest test is the closest available proxy for a full recompute plus a write.

Break-even is the builds per week at which a cron table costs what the model's
current prod tests cost: `prod_slot_hours / build_hours`.

| Mart                           | prod now | build | break-even | cron                    | prod after |
| ------------------------------ | -------: | ----: | ---------: | ----------------------- | ---------: |
| `bridge_survey_expectations`   |     12.4 |   43m |      17/wk | `0 3 * * *`             |        5.0 |
| `fct_survey_submissions`       |     23.2 |   30m |      47/wk | `0 3 * * *`             |        3.5 |
| `fct_survey_responses`         |      0.0 |   32m |        n/a | `0 3 * * *`             |        3.8 |
| `dim_survey_administrations`   |      0.0 |   13m |        n/a | `0 3 * * *`             |        1.5 |
| `dim_college_enrollments`      |     13.4 |    4m |     183/wk | `0 3 * * *`             |        0.5 |
| `fct_grades_assignments`       |      0.0 |    7m |        n/a | `0 3 * * *`             |        0.8 |
| `fct_support_tickets`          |     11.6 |   10m |      71/wk | `0 3 * * *`             |        1.1 |
| `fct_student_attendance_daily` |      1.7 |   14m |       8/wk | `0 0,10,13,15,17 * * *` |        7.9 |
| `dim_staff_reporting_chain`    |     22.3 |   18m |      75/wk | `0 0,10,13,15,17 * * *` |       10.4 |
| `dim_staff_work_history`       |      9.6 |    7m |      83/wk | `0 0,10,13,15,17 * * *` |        4.0 |

The result is 2 cadences, but each is derived rather than assumed. Daily
`0 3 * * *` goes to the 7 marts with no live reader. The assessment-mart tick
`0 0,10,13,15,17 * * *` goes to the 3 that Cube reads.

Build minutes above are rounded for display while break-even is computed from
the unrounded value, so a few rows do not reproduce exactly from the printed
columns. `dim_college_enrollments` is the widest gap, 183/wk against 201/wk from
the rounded 4m. No row is close enough to its cadence for the rounding to change
a decision.

4 of the 7 daily models sit far below their break-even. The other 3 —
`fct_survey_responses`, `dim_survey_administrations` and
`fct_grades_assignments` — have no break-even to clear: they cost 0.0 prod slot
hours today, so a nightly cron is a pure prod add of 6.1 slot hours a week
between them. They are justified by their CI column alone, which is 181.4 hours
a week combined.

**`fct_student_attendance_daily` knowingly costs more in prod**, 1.7 to 7.9 slot
hours a week, because 35 builds a week exceeds its 8/wk break-even. Its Cube
consumer anchors topline Total Enrollment and needs the intraday tick. Its CI
column drops from 90.5 to about 21, so the model still reduces total cost.

### Expected result

A CI run today creates the view for free and then runs every attached test
against it. After the change it builds the table once and the tests are cheap.
So CI cost per model scales by `build_minutes / (n_tests * avg_test_minutes)`,
computed per model rather than as one blanket factor.

| Mart                           | CI now | CI after |
| ------------------------------ | -----: | -------: |
| `bridge_survey_expectations`   |  281.0 |       84 |
| `fct_survey_submissions`       |  215.3 |       58 |
| `fct_survey_responses`         |  105.8 |       60 |
| `fct_student_attendance_daily` |   90.5 |       21 |
| `dim_survey_administrations`   |   37.9 |       15 |
| `fct_grades_assignments`       |   37.7 |       11 |
| `dim_college_enrollments`      |   27.0 |        8 |
| `fct_support_tickets`          |   23.0 |        6 |

`fct_survey_responses` wins least, 105.8 to 60, because it carries only 2 tests
and its build is nearly as expensive as one of them. It still clears, but it is
the weakest member of the batch.

Totals: prod 94 to 38, CI 818 to about 263. That is about 610 slot hours a week,
or 21% of all warehouse compute in the project.

### Live consumers

Only 3 of the 10 have a reader today.

| Mart                           | Read by                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `fct_student_attendance_daily` | Cube `student_enrollments` and `student_attendance` cubes          |
| `dim_staff_work_history`       | Cube `staff_work_history` cube                                     |
| `dim_staff_reporting_chain`    | `src/cube/cube.js:145`, per user session, for the PII access scope |

The other 7 have no `sql_table` pointing at them anywhere in `src/cube/model/`.
They appear only in the `cube.yml` exposure `depends_on`, which covers the
semantic layer as a whole. No Tableau exposure references any of the 10, so no
Tableau refresh cron sets a freshness floor on this batch.

That inventory method — grep `src/cube/model/` for `sql_table`, plus Tableau
exposures — finds external consumers and misses in-dbt ones by construction.
`fct_student_attendance_daily` has one: `rpt_branchingminds__daily_attendance`
reads it and feeds a vendor SFTP job at `0 3 * * *`. The conclusion survives,
because that mart took the intraday tick anyway and none of the other 7 has a
downstream dbt model outside this batch. But "no reader" here means no reader
found by that method, not no reader.

`dim_staff_reporting_chain` deserves separate attention. `cube.js` runs
`SELECT reportee_staff_key FROM kipptaf_marts.dim_staff_reporting_chain WHERE manager_staff_key = @k`
on each user session, 26 times in 7 days at 16.1 slot minutes a call. That is a
recursive closure recomputed inside session setup. The table conversion removes
it as a latency source, not only as a cost.

## What does not need doing

All 10 already declare their foreign keys as `columns[].config.meta.foreign_key`
rather than real `constraints: - type: foreign_key`. Verified: zero occurrences
of `type: foreign_key` across the 10 properties files. The
[#4821](https://github.com/TEAMSchools/teamster/issues/4821) migration is
already complete on this batch, so no FK constraint work is required and no FK
closure has to be converted alongside.

9 of the 10 inherit `contract: enforced: true`, which is correct for a table and
needs no change; their column lists already carry `data_type`.
`dim_staff_reporting_chain` already sets `contract: enforced: false`.

A table mart needs `warn_unenforced: false` on its `primary_key` constraint,
because the constraint renders into the CREATE TABLE DDL and warns otherwise.
That is the only per-column edit this change requires.

## Risks and gates

### Size is unmeasured and gates the merge

`bridge_survey_expectations` is a scaffold whose family branch is a `cross join`
from survey administrations to every contact person. As a view that costs
compute; as a table it costs storage permanently.

Build each of the 10 into a dev schema and record its row count and bytes
**before** merging its properties yml. Do not estimate.

Do not run `count(*)` against these views to get the number. One attempt over 4
of them consumed 100,540 slot minutes across 52 minutes and failed with
`billingTierLimitExceeded`.

### The prod migration wedges if it is left to the sensor

A config-only properties yml change does not fire `code_version_changed` at
deploy, because `code_version` is a SHA1 of the model's raw SQL and the SQL does
not change. The automation sensor therefore never selects these models.

Worse, view to table DROPS the view before it creates the table. A sensor that
materializes assets one at a time and out of order leaves dependents
drop-failing every tick and MISSING from prod, which reads as absence from
`kipptaf_marts.__TABLES__` rather than as stale data.

Finish post-merge with ONE Dagster `launch_run` selecting all 10 assets. That is
a single `dbt build`, which dbt topologically sorts. This is the failure mode
that got [#4464](https://github.com/TEAMSchools/teamster/issues/4464) reverted
by [#4587](https://github.com/TEAMSchools/teamster/issues/4587).

### `dim_staff_reporting_chain` must not be missing when Cube asks

Between the view drop and the table create, `cube.js` resolves an empty reportee
set and denies PII access as if the manager had no downline. Convert it in the
same ordered run and confirm the relation exists before the next Cube session.

### Cron cadence degrades FK orphan detection, and the repo has hit this before

A view mart is recomputed at test time, so a `relationships` test compares a
child derived from current upstream data against a parent rebuilt moments
earlier. The two are structurally in sync. A cron table is a snapshot instead —
up to 24 hours old for the nightly 7, about 5 for the intraday 3 — while its FK
parents stay eager. `dim_staff` rebuilds 192 times a week. Every key it drops
between child ticks leaves the stale child referencing it, and the test reports
an orphan that is a cadence artifact rather than a data defect.

This is the failure `dim_assessments` already hit. Its properties yml records
being raised from nightly to 5x/day under
[#4559](https://github.com/TEAMSchools/teamster/issues/4559) precisely to close
a skew window against `dim_assessment_administrations`. This change reintroduces
that shape at larger scale and does not apply the same remedy, because the 7
nightly marts have no consumer that justifies the extra builds.

Nothing breaks: these tests are `severity: warn` by the project default. The
cost is signal quality, and it lands on top of the orphan failures already
tracked for `fct_student_attendance_daily` in
[#4229](https://github.com/TEAMSchools/teamster/issues/4229), making that class
harder to triage rather than easier. The 7-day follow-up measurement should
check whether orphan counts moved after the conversion, not only slot hours.

### Student data becomes persisted at rest

`fct_grades_assignments` (23.4M rows) and `fct_student_attendance_daily` (12.6M
rows) are student-level education content under the repo's PII rules. As views
they held no data; as tables they persist it in `kipptaf_marts`. That changes
the IAM surface, and it means an upstream deletion is not reflected until the
next cron tick. Neither is a reason not to proceed — every existing table mart
carries the same property — but it is a new fact about this dataset.

### Recursion is not a blocker

`dim_staff_reporting_chain` uses `WITH RECURSIVE`. That is compatible with a
table: `int_illuminate__root_standards` is `WITH RECURSIVE` plus
`materialized: table` and holds 569,847 rows in prod today. Only dbt's contract
validation subquery wrapper breaks recursion, and contract enforcement is
already off on this model.

## Verification

1. For each of the 10, the dev build recorded a row count and a byte size, and
   both are acceptable.
2. `kipptaf_marts.__TABLES__` reports `type = 1` for all 10 after the ordered
   prod run, with a `last_modified_time` from that run.
3. A follow-up `JOBS_BY_PROJECT` query 7 days after merge shows the same 10
   marts at roughly the projected slot hours, split prod and CI by
   `target_name`.
4. Cube still resolves a non-empty reportee set for a manager with known direct
   reports.

## Out of scope

**`--indirect-selection=cautious`** at
`src/teamster/libraries/dbt/assets.py:112` would remove 72.3 of the 117.5 weekly
prod test slot hours. It is rejected for this change on 3 grounds. It does
nothing for CI, which selects both parents and so behaves identically under
`eager` and `cautious`, and CI is 90% of the cost here. It is repo-wide, because
`build_dbt_assets()` is called by all 5 code locations. It trades away
parent-side FK orphan detection on every view mart, dropping those checks from
roughly 9 a day to only when that model's own SQL changes. Once these 10 are
tables, its savings on them evaporate.

**The remaining 57 view marts.** Each costs at most 6.1 slot hours a week.
Revisit only if the measurement in step 3 shows the tail grew.

**`bridge_survey_expectations` SQL.** Its `cross join` scaffold is worth
questioning, but it measured 0.017 GB, so there is no cost argument for touching
it here.

**`fct_grades_assignments`'s stale duplicate-key TODO.** The model carries an
in-file `TODO` citing 71 residual duplicate keys from `stg_powerschool__cc`
double-writes. The data no longer supports it —
[#4017](https://github.com/TEAMSchools/teamster/issues/4017) is closed and the
table measures 23,437,020 rows against 23,437,020 distinct keys — but removing a
comment is a separate change from this one.

## Scope amendment: one SQL fix

This change was scoped as materialization-only. It is not, by a deliberate
decision taken after the dev build.

The build surfaced 2 marts whose `primary_key` constraint their own data
violates. That is harmless on a view, where constraints are inert, but
`materialized: table` renders the constraint into DDL, and BigQuery documents
that "queries over tables with violated constraints might return incorrect
results" — the optimizer uses unenforced keys for join elimination and
reordering. Shipping a table that declares a key 46,062 rows contradict is worse
than shipping the view it replaces.

Both shared a single root cause, fixed here in about 20 lines of
`fct_survey_submissions.sql`. `int_surveys__manager_survey_details` is
question-grain; the `historic_archive_submissions` CTE read it without
projecting to submission grain, so the historic Alchemer archive emitted 18 rows
per submission and collided 2,559 `survey_submission_key` values.
`fct_survey_responses` inner-joins on that key, so its rows fanned out 18x in
turn. The fix applies the same `dbt_utils.deduplicate` projection that
`manager_subject_overlay` already uses on the same source, 40 lines earlier in
the same model, and is information-preserving — every column the CTE selects is
constant within the partition across all 2,559 submissions.

Row counts move as a result: `fct_survey_submissions` 92,459 to 48,956, and
`fct_survey_responses` 1,363,717 to 580,663. Both PK uniqueness tests now pass.
Measurements in `docs/superpowers/plans/baseline-2026-09-11.md`.

The prod and CI slot-hour claims in this document still hold — they are measured
from test slot time before the fix, and the fix does not change how often a test
runs. The per-model build minutes are now slightly stale for the 2 fixed marts,
since `fct_survey_responses` processes less than half its former row count and
gains a `group by`. That moves its break-even and its CI-after estimate in the
cheaper direction, and it is nightly with no break-even to clear, so no cadence
decision changes. The 7-day follow-up re-measures all of it anyway.

What did change is the row sets. The conversion is no longer verifiable as a
pure materialization change, so the row deltas above — not just object type and
slot hours — are what to check after deploy.
