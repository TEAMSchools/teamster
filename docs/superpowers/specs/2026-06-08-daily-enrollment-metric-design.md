# Point-in-time daily student enrollment metric

Issue: [#4138](https://github.com/TEAMSchools/teamster/issues/4138)

> **Final naming + scope (decided post-implementation).** This spec uses working
> names `student_enrollment_daily*` for the new cube/views and
> `student_enrollments*` for the stint cube/views. As shipped: the daily fact
> cube is `student_enrollments` with views `student_enrollments_summary` /
> `_detail`; the stint dim cube is `student_enrollment_stints` (no views — see
> below). The dbt mart is unchanged (`fct_student_enrollment_daily`).
> `student_attendance`'s join to the stint dim was repointed
> `student_enrollments` → `student_enrollment_stints`.
>
> **Stint views removed.** The stint summary/detail views were dropped (only the
> point-in-time daily surface is used). The stint **cube** remains as the
> enrollment dimension in the join graph. Stint-grain attributes still wanted as
> breakdowns of the point-in-time headcount — ELL/IEP/meal status,
> `graduation_year`, `is_retained_year` — are surfaced on the daily
> `student_enrollments` views via the `student_enrollment_stints` join path
> (they are stint-grain, documented as such). The stint measure
> `count_enrollments` and the entry/exit dates are no longer exposed.

## Problem

The Cube measure `student_enrollments.count_students` counts enrollment _stints_
— `count_distinct(student_enrollment_key)` on `dim_student_enrollments`. That
population is alumni-inclusive, spans all academic years, and has no
point-in-time concept. It does not reconcile with the topline dashboard's
`Total Enrollment` metric, which counts students enrolled in a given week via
`sum(if(is_enrolled_week, 1, 0))` from
`int_extracts__student_enrollments_weeks`.

Analysts want period-over-period comparisons of enrolled-student counts that
match the topline numbers, **and** day-exact answers to questions like "what was
enrollment on October 1" (the NJ state fall-enrollment count date). Today Cube
gives them neither.

### Reconciliation (AY2025, network-wide)

| Definition                                                | Count  |
| --------------------------------------------------------- | ------ |
| Cube `count_students` (distinct `student_enrollment_key`) | 14,996 |
| Distinct students (`student_key`)                         | 14,890 |
| Stints with non-null dates (drop alumni placeholders)     | 11,384 |
| Point-in-time enrolled, one recent week                   | 9,114  |

The stint count is ~64% higher than a true point-in-time headcount.
Decomposition of the gap:

- **−106** multi-stint students (the `count_distinct(student_key)` swap fixes
  only this — negligible).
- **−3,612** alumni / graduate placeholder rows with null dates (the dominant
  driver, ~24% of the stint count).
- **−~2,300** point-in-time effect: students with an AY2025 stint who were not
  enrolled in the specific period measured.

## Why day grain, not week grain

An earlier draft of this spec proposed a weekly fact over
`int_extracts__student_enrollments_weeks`. Day grain supersedes it for one
decisive reason: **"what was enrollment on October 1" cannot be answered at week
grain.** A weekly row says "enrolled some day this week"; a student who entered
Wednesday Oct 2 or exited Monday Sep 30 is indistinguishable from one enrolled
all week. October 1 is not a casual example — it is the NJ state fall-enrollment
count date (alongside Oct 15 and Mar 15), and there are already day-exact
`is_enrolled_oct01` / `oct15` / `mar15` flags derived upstream as
`date(academic_year, 10, 1) between entrydate and exitdate`
([`int_powerschool__student_enrollment_union`](../../../src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_enrollment_union.sql)).

A day-grain fact generalizes those one-off flags: every named count date becomes
a plain `where date_key = '<date>'` filter, weekly/monthly/yearly trends come
from the period-end anchors, and the topline weekly reconciliation still works
by filtering to the days of one week. One grain answers all three question
shapes; the named flags become unnecessary.

This is the same shape `fct_student_attendance_daily` already has — student ×
in-session-day, anchored — so the design mirrors a proven precedent rather than
inventing one.

### Coverage decision: in-session school days only

One row per enrolled student per **in-session school day** (the
`dim_school_calendars` / `stg_powerschool__calendar_day` grain,
`insession = 1`), not every calendar day. Matches the attendance membership
grain exactly. "Enrolled on Oct 1" is answerable whenever Oct 1 is a school day
(it always is for the fall count date); an arbitrary non-session date (a
Saturday) correctly returns no row.

## Why not reuse `fct_student_attendance_daily`

It is already student × in-session-day with `membership_value` and the three
anchors — superficially a drop-in. But it is **not** an authoritative enrollment
source:

- It nulls Paterson `membership_value` / `attendance_value` before AY2026
  (explicit
  `if(_dbt_source_project = 'kipppaterson' and academic_year < 2026, null, ...)`
  in the fact SQL).
- It only spans days the ADA pipeline (`int_powerschool__ps_adaadm_daily_ctod`)
  produced — exactly the days enrollment must be complete and independent of.

So enrollment gets its own fact, expanding stints against the complete
per-school calendar, not the attendance-recorded subset.

## Why not just join the existing cube to a date scaffold

Cube cannot expand the stint table into a daily grain on the fly:

- Cube has **no non-equi / BETWEEN join** (`src/cube/CLAUDE.md`). A
  `date BETWEEN entrydate AND exitdate` join is not expressible.
- A Cube dimension cannot reference a measure; "classify an aggregate by a
  data-driven range" is explicitly unsupported.
- A `many_to_one` BETWEEN from stint to dates would fan a stint into N day-rows
  and silently mis-aggregate, because Cube's fan-trap protection trusts the
  declared relationship.
- The period-end anchors are `row_number()` windows over the student-day grain —
  window functions, which Cube cannot express (`src/cube/CLAUDE.md`:
  transformation lives in a dbt mart read via `sql_table`).

The expansion and the anchors therefore belong in a dbt mart.

## Why a separate cube, not an extension of `student_enrollments`

A reasonable instinct is "all our new measures are date-bound, so fold them into
the existing `student_enrollments` cube instead of standing up a parallel one."
The architecture forbids the literal forms of that, for three linked reasons:

- **`student_enrollments` is a dimension, not a fact.**
  `dim_student_enrollments` is PK'd one row per enrollment _stint_
  (`hash(student_number, _dbt_source_project, academic_year, entrydate)`). It
  plays the dimension role in the star schema: `student_attendance` joins it
  `many_to_one` for location / region / grade / demographics
  ([student_attendance.yml](../../../src/cube/model/cubes/student_attendance/student_attendance.yml)),
  and both attendance views traverse it. The new fact is a different grain — one
  row per stint × in-session day (~180×). One table cannot be both grains.
- **Repointing the cube at day grain breaks the join graph.** If
  `student_enrollments` read `fct_student_enrollment_daily`, every existing
  `many_to_one` join into it (attendance, and its views) would silently become
  `many_to_many`. Cube's fan-trap protection trusts the _declared_ relationship,
  so attendance measures would mis-aggregate with no error.
- **Date-bound measures need day rows to bind to — which the stint cube lacks.**
  A measure like "enrollment on Oct 1" filters `where date_key = '<date>'`; the
  stint dim has only `entry_date` / `exit_date` endpoints, no per-day spine.
  Binding a date to a stint requires `BETWEEN entry_date AND exit_date` — the
  non-equi operation Cube can't express (the constraint above). The
  date-boundedness is exactly what _forces_ the separate day-grain fact, not
  what makes it mergeable.

The star-schema-correct reading of "incorporate into the existing cube" is **a
new fact cube that joins the existing enrollment dimension** — which is what
Components 1–2 do: the daily fact FKs the same `student_enrollments` /
`students` / `locations` dims (no duplication). There is still exactly one
enrollment dimension network-wide; the daily fact hangs off it, parallel to how
`student_attendance` already does. Only the grain — and therefore the table, and
therefore the cube — is necessarily separate.

### Measure naming: the stint measure is a stint counter, not a kid counter

The two cubes answer different questions and **must not share the
`count_students` name** — the name is the strongest documentation, and today the
stint measure is actively mis-labeled (its summary view tells analysts to
"always use `count_students` for enrollment headcounts," which is false — it
counts enrollment records, not distinct students: 14,996 stints vs 14,890
students vs 9,114 point-in-time enrolled).

This spec therefore **renames the existing stint measure**
`student_enrollments.count_students` → `count_enrollments`
(`count_distinct(student_enrollment_key)` — one count per enrollment _stint_,
alumni-inclusive, all-years) and **reserves `count_students` for the new daily
cube**, where it is an honest per-period distinct-student headcount. After the
rename:

- `student_enrollments.count_enrollments` — "how many enrollment records," not a
  headcount. Gets a `description:` saying exactly that (the measure has none
  today).
- `student_enrollment_daily.count_students` — point-in-time student headcount,
  valid only when a period is pinned (date filter or `_*_end` anchor).

This is a breaking rename of a live measure, but the blast radius is contained:
`student_enrollments.count_students` is referenced only in its own cube and its
two views (`student_enrollments_summary` / `_detail`) — no Tableau extract or
dbt exposure consumes it by name (verified 2026-06-09). The rename, the new
`description:`, and the corrected view guidance (drop "always use … for
headcounts"; point headcount/point-in-time questions at the daily cube) all land
in this PR's implementation step.

## Design

### Component 1 — mart `fct_student_enrollment_daily`

A fact in `src/dbt/kipptaf/models/marts/facts/` that expands enrollment stints
against the in-session school calendar and stamps the three day-grain anchors.
This is the direct analog of
[`fct_student_attendance_daily`](../../../src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql)
— same join shape (stints ⋈ per-school calendar days), same anchor windows.

Grain: one row per `(student_enrollment_key, date_key)` — one in-session day per
enrolled student-stint.

Build shape (mirrors the attendance fact):

```sql
-- stints ⋈ in-session calendar days
from {{ ref("int_powerschool__student_enrollment_union") }} as enr
inner join {{ ref("stg_powerschool__calendar_day") }} as cd
    on cd.schoolid = enr.schoolid
    and cd.date_value >= enr.entrydate
    and cd.date_value < enr.exitdate      -- half-open; see src/dbt/CLAUDE.md
    and {{ union_dataset_join_clause(...) }}  -- or _dbt_source_project equality
where cd.insession = 1
```

Columns:

- `student_enrollment_daily_key` — PK,
  `generate_surrogate_key([student_number, _dbt_source_project, date_key])`
  (mirrors attendance's `student_attendance_daily_key` shape).
- `student_enrollment_key` — FK to `dim_student_enrollments`, hashed identically
  (`student_number, _dbt_source_project, academic_year, entrydate`) so the fact
  joins the existing enrollment dim **and** serves as the anchor window
  partition key. Derived in a CTE — the calendar-day spine does not carry it
  (Open item A).
- `student_key` — FK to `students` (`dim_students`).
- `location_key` — FK to `locations` (`dim_locations`), via `schoolid` →
  `stg_powerschool__schools` like `dim_student_enrollments` does.
- `date_key` — DATE = `cd.date_value`, FK to `dim_dates`.
- `academic_year` — **sourced from the calendar term, not the stint.** Join the
  calendar day to `stg_powerschool__terms`
  (`date_value between firstday and lastday`, per school) and take the term's
  `academic_year`, so `date_key` and `academic_year` are consistent by
  construction. Copying `enr.academic_year` from the stint would mislabel the
  122 of 11.7M AY2024+ rows where a stint's date falls in a different school
  year than the stint's own label (verified 2026-06-09) — and that mislabeling
  is exactly the year-mixing that would break the `mar15` count (March 15
  belongs to the prior-July academic year under the KIPP convention). The terms
  join can match multiple term rows per day (slight fan-out observed); pick one
  deterministically (e.g. `portion = 4` quarters, or `isyearrec = 1`) so the
  grain stays one row per `(student_enrollment_key, date_key)`.
- `grade_level` (degenerate dim for filtering). Region is **not** a fact column
  — it resolves through the `locations` → `regions` join in the view (Component
  3).
- `enroll_status` — INT64, carried from the stint (0 active / 2 withdrawn / 3
  graduated). Student-level (identical across all of a student's rows), used
  only by the `count_students_active` measure. Document the student-level caveat
  in the column description (it is not a point-in-time status).
- `is_enrolled` — INT64 1 for every row (each row is an enrolled in-session day;
  per marts R3, a countable flag). Row marker, not the count base — measures use
  `count_distinct(student_key)`, not `sum(is_enrolled)` (see Component 2).
- Anchor flags (INT64 0/1) — these are **calendar-derived, per-school
  period-last-day markers**, NOT per-student `row_number()` windows. A row's
  anchor is true when its `date_key` equals the school's last in-session day of
  that period. They mark "is this the period's last day" (a calendar property,
  same for every enrolled student at the school), so a student who withdrew
  mid-period has no row on the period's last day and correctly drops from a
  period-end count — that is the "still enrolled at period end" semantic. **All
  anchors are per-school** (not network-global): verified 2026-06-09 that
  schools share a month-end mid-year (Oct: all 22 schools → 2025-10-31) but
  **diverge at year-end** (June: 4 distinct last days, Miami 2026-06-04 vs
  others to 2026-06-29). A network-global "last day" would silently drop
  early-ending schools (Miami) — the per-school anchor counts each as of its own
  last day.
  - `is_current_record` —
    `date_key = least(<school's max in-session date for this academic_year>, current_date('America/New_York'))`.
    The school's last in-session day that **has actually occurred**. For a
    completed year this is the school's June last day; for the **current** year
    it is today (the future June days don't exist as rows yet, so a static
    "school year last day" anchor would return ~0 mid-year — this
    `least(..., current_date)` cap is what makes the default work live).
    **Build-time dependent**: like the upstream `is_current_week_mon_sun`, this
    flag shifts as `current_date` advances, so the daily mart rebuild keeps it
    current; it is non-deterministic across build dates for the in-progress year
    (static for completed years). Drives the default `count_students` at year /
    no-grouping (AY2025 → 10,374 as of each school's latest occurred day; AY2023
    → 9,630 true year-end; verified 2026-06-09).
  - `is_month_end_record` —
    `date_key = least(<school's last in-session day of the calendar month>, current_date)`.
    Per `(school, month)`.
  - `is_week_end_record` —
    `date_key = least(<school's last in-session day of the ISO week>, current_date)`.
    Per `(school, week)`. **At day grain this is a real anchor** (the no-op
    concern that dogged the weekly design is gone — a week has multiple
    day-rows, exactly one of which is the week-end).

  **All three period anchors share one rule:**
  `date_key = least(<school's last in-session day of the period>, current_date('America/New_York'))`,
  where period ∈ {academic year (`is_current_record`), month, week}. Per-school,
  capped at today. The current (in-progress) period anchors to today; completed
  periods anchor to their true last day. Without the `current_date` cap, the
  current week/month/year bucket would be empty (its last day is in the future —
  verified 2026-06-09: today Jun 9, current week-end Jun 12, current month-end
  Jun 29), so the cap is required for all three, not just the year. This mirrors
  how the attendance snapshot guard treats the current period.
  - `is_latest_record` — per-student last enrolled in-session day,
    `row_number() over (partition by student_enrollment_key order by date_key desc) = 1`.
    Partition by `student_enrollment_key` (which encodes `academic_year`), so it
    is year-scoped. This is **NOT** a period-end marker — it is each student's
    own last enrolled day, which exists for anyone ever enrolled, so it drives
    the `count_students_served` measure (ever-enrolled), not the period-end
    default. Keep it distinct from `is_current_record`.

Materialization: `config: materialized: table` (in the properties yml) —
overrides the marts `view` default. At ~18.9M rows with `row_number()` windows
(see "Resolved decisions" E), a view would re-expand on every Cube query.

Tests: `unique` on `student_enrollment_daily_key` (or
`dbt_utils.unique_combination_of_columns` on the hash inputs); `relationships`
on each FK; singular tests (`tests/test_*.sql`) for the single-row anchor
invariants — exactly one `is_latest_record` per `student_enrollment_key`, one
`is_week_end_record` per `(student_enrollment_key, iso-week)`, one
`is_month_end_record` per `(student_enrollment_key, month)`.

### Component 2 — cube `student_enrollment_daily`

`src/cube/model/cubes/students/student_enrollment_daily.yml`, `public: false`,
`sql_table: kipptaf_marts.fct_student_enrollment_daily`.

- Dimensions: PK, the three FKs (`relationship: many_to_one` joins to
  `students`, `locations`, `student_enrollments`), `date` (cast to TIMESTAMP per
  cube time-dimension rule), `academic_year`, `grade_level`, and the three
  `is_*_record` anchors + `is_enrolled`. Region and grade-level breakdowns come
  through the `students` / `locations.regions` join paths in the view — no
  degenerate `region` dim on the cube (this is the attendance convention).
- **All measures are `count_distinct(student_key)`, not `sum(is_enrolled)`.**
  This matters: at a single pinned day the two agree (verified 2026-06-09: Oct 1
  2025 → 10,637 rows = 10,637 distinct stints = 10,637 distinct students, no
  same-day concurrent stints), but over a multi-day window `sum` yields
  student-_days_ (a week → ~51,837) while `count_distinct` yields a sensible
  unique-student count (~10,654). `count_distinct` degrades gracefully when
  under-specified — the worst an analyst gets is "distinct students enrolled at
  some point in the queried window," a real metric, not garbage. This matches
  the attendance CA measures, which are also `count_distinct`. `is_enrolled`
  stays on the fact as the row marker, but the measures count distinct students.
  **Measure model — period-end-as-of-now is the default, "served" is the named
  escape hatch.** The bare `count_students` is governed by the `cube.js`
  snapshot guard (it goes _into_ `SNAPSHOT_MEASURE_STEMS`), so it is **always a
  point-in-time snapshot as of the last active in-session day of whatever period
  the query groups by, capped at today** — never an unanchored day-sum and never
  an "ever-enrolled" count. The guard injects the matching anchor by
  granularity, with the per-school, `current_date`-capped flags from Component
  1:
  `SNAPSHOT_ANCHOR_DIMENSIONS = {default: is_current_record, month: is_month_end_record, week: is_week_end_record}`.
  (Note the `default` is `is_current_record`, **not** `is_latest_record` — the
  period-end-as-of-now flag, not the per-student-last-day flag.) "How many
  students in 2025" returns the headcount as of each school's last active day;
  "by month" each month-end; a pinned date that day.
  - `count_students`: `count_distinct(student_key)`. **In
    `SNAPSHOT_MEASURE_STEMS`.** By granularity:
    - no time grouping (e.g. `academic_year = 2025`) → `is_current_record` →
      enrolled as of each school's last occurred in-session day (AY2025 →
      10,374; AY2023 → 9,630).
    - granularity `month` → `is_month_end_record`; `week` →
      `is_week_end_record`.
    - single `date_key` pin → that exact day (~10,637 on 2025-10-01).

    All point-in-time, all `count_distinct(student_key)`. The stint cube's
    counter is renamed `count_enrollments` (see "Measure naming"). **Do not
    filter `enroll_status`** — it is student-level and would drop a mid-year
    withdrawal from days they were still enrolled. Because the default IS
    year-end-as-of-now at year grain, **no separate `count_students_year_end`
    measure is needed** — `count_students` filtered to a completed year already
    gives that year's year-end (per-school last day); for the current year it
    gives as-of-today.

  - `count_students_served`: `count_distinct(student_key)` with measure filter
    `{CUBE}.is_latest_record = true`, **self-anchored suffix so the guard leaves
    it alone**. Counts distinct students enrolled **at any point** in the
    queried period — "ever enrolled" (AY2023 10,381, AY2025 11,261; verified
    2026-06-09). `is_latest_record` is year-scoped (partitioned by the
    academic-year-encoding `student_enrollment_key`), so each served student has
    exactly one flagged row per year and the distinct count is exact. The
    difference from the default (10,381 served vs 9,630 year-end for AY2023) is
    the ~750 within-year leavers — the deliberate "students we served" question
    vs "still enrolled at period end."
  - `count_students_active`: `count_distinct(student_key)` with measure filter
    `{CUBE}.enroll_status = 0`, self-anchored (guard leaves it alone).
    Active-status headcount (~10,374 for AY2025 — note it ≈ the date-membership
    default for the current year, an independent cross-check). Needed for a
    downstream use; **by design does NOT match topline**. Caveat:
    `enroll_status` is student-level, so for a _past_ date it reflects the
    student's _current_ status, not status on that date — current-roster
    questions only, not historical point-in-time.

- **Named state-count-date measures — filter, do NOT add fact flags.** The
  regulatory count dates (`oct01`, `oct15`, `mar15`) are filterable date
  predicates at day grain, not row properties. Expose them as named measures
  (discoverable in BI, analogous to the `_*_end` anchor measures), each
  `count_distinct(student_key)` with a measure filter on `date_key`:
  - `count_students_oct01`: filter
    `extract(month from {CUBE}.date_key) = 10 and extract(day from {CUBE}.date_key) = 1`.
  - `count_students_oct15`: month 10, day 15.
  - `count_students_mar15`: month 3, day 15.

  **Filter on the row's own month/day, never on `academic_year + 1`.** Each fact
  row already carries the correct `academic_year` (sourced from the calendar
  term — see Component 1) and a real `date_key`, so March 15 2026 self-labels as
  `academic_year = 2025` (KIPP July–June convention; verified 2026-06-09 that
  AY2025 spans 2025-07-01 → 2026-06-30 and contains both 2025-10-01 and
  2026-03-15). The upstream `is_enrolled_mar15 = date(academic_year + 1, 3, 15)`
  arithmetic exists only because the _stint_ row knows just its start year; the
  day-grain row needs no such adjustment, which is exactly what removes the
  year-mixing risk. A multi-year query (`group by academic_year`) then returns
  one correct Oct-1 / Mar-15 headcount per school year with no `+1` bookkeeping.

- **Do NOT materialize `is_oct01` / `is_mar15` flags on the fact.** They would
  store three INT64 columns of information already in `date_key` (redundant on
  an ~18.9M-row table), and a change to a count date would force a full rebuild
  instead of a one-line measure edit. Keep them as measure filters.
- A date join to `dates` on `date_key` for day/week/month/quarter granularity in
  the view. The day-grain `date` dimension is itself the answer to "enrollment
  on a specific date" — a single-date filter on `count_students` answers any
  arbitrary date (not just the named ones) and needs no anchor.

#### Measure descriptions (paste into the cube YAML `description:` fields)

Production-ready text — self-contained so an analyst reading only the BI field
list understands the measure and its footguns. Use verbatim.

- **`count_students`** — "Distinct students enrolled, point-in-time. Counts each
  student once as of the most recent in-session school day in your query: the
  exact date if you filter to one, otherwise each school's latest in-session day
  in the period (today for the current year, the last day of school for
  completed years). Matches the topline Total Enrollment methodology —
  enrollment is by entry/exit dates, not status. Note: when no single date is
  pinned, schools that end on different days are each counted as of their own
  last day, so a network total can mix as-of dates within the final weeks of a
  year. For 'how many students did we serve at any point' use
  count_students_served; for active-status roster use count_students_active."

- **`count_students_served`** — "Distinct students enrolled at any point during
  the queried period. A student who enrolled and then withdrew mid-year is still
  counted. Use for 'how many students did we serve this year.' This is higher
  than count_students (point-in-time) by the number of mid-period
  enrollments/withdrawals. Not a point-in-time headcount — for that use
  count_students."

- **`count_students_active`** — "Distinct students with an active enrollment
  status (excludes withdrawn and graduated). Use for current active-roster
  questions. WARNING: enrollment status is the student's current status, not
  their status on a past date — do not use this for historical point-in-time
  counts (use count_students with a date filter). Does not match topline Total
  Enrollment, which counts by enrollment dates rather than status."

- **`count_students_oct01` / `count_students_oct15` / `count_students_mar15`** —
  "Distinct students enrolled on the [October 1 / October 15 / March 15] state
  count date of the queried academic year. Point-in-time headcount for the
  regulatory fall/spring enrollment count. Group by academic_year to compare
  count dates across years. (March 15 falls in the spring of the academic year —
  e.g. academic_year 2025 = March 15, 2026 — and is handled automatically.)"

`cube.js` wiring:

- **No domain-gating edit needed.** Access gating is prefix-derived
  (`isStudentMember = (m) => m.startsWith("student")`,
  [cube.js](../../../src/cube/cube.js)); the cube name
  `student_enrollment_daily` is gated automatically. The old `STUDENT_CUBES`
  array no longer exists.
- Append `"student_enrollment_daily"` to `SNAPSHOT_CUBES`.
- Add the `count_students` stem to `SNAPSHOT_MEASURE_STEMS` so the guard governs
  the base measure (this is the inversion from attendance, where the bare count
  is unanchored). `count_students_served` and `count_students_active` carry a
  `SNAPSHOT_SELF_ANCHORED_SUFFIXES` suffix (e.g. `_served`, `_active`) so the
  guard leaves them alone — **add `_served` and `_active` to that array** (today
  it holds `_year_end` / `_month_end` / `_week_end`).
- **`cube.js` per-cube default anchor — small, isolated, additive change.** The
  guard's `SNAPSHOT_ANCHOR_DIMENSIONS.default` is hardcoded `is_latest_record`;
  this cube needs the no-granularity default to inject **`is_current_record`**
  (per-school period-end-as-of-now), not `is_latest_record` (per-student last
  day = served). Make the anchor map per-cube with fallback to the shared map,
  so attendance's resolved map is byte-for-byte unchanged:

  ```js
  const SNAPSHOT_ANCHOR_OVERRIDES = {
    student_enrollment_daily: { default: "is_current_record" },
  };
  // in the loop, per cubePrefix:
  const anchorMap = {
    ...SNAPSHOT_ANCHOR_DIMENSIONS,
    ...(SNAPSHOT_ANCHOR_OVERRIDES[cubePrefix] ?? {}),
  };
  const anchorDimension = anchorMap[granularity] ?? anchorMap.default;
  ```

  Also change the `alreadyAnchored` check's
  `Object.values(SNAPSHOT_ANCHOR_DIMENSIONS)` to `Object.values(anchorMap)` so a
  manually-supplied `is_current_record` filter is recognized as
  already-anchored. Scope: **3 lines, the anchor-_selection_ logic only — NOT
  the access-control / location-scope path of `queryRewrite`, which is
  untouched.** Add a hooks/cube regression check that attendance's injected
  anchors are unchanged.

- **Quarter granularity is unsupported by the guard**
  ([cube.js](../../../src/cube/cube.js) rejects granularities outside
  day/week/month) — same limit attendance has. Document that enrollment
  quarter-trends aren't available; use month.
- The cube must expose `is_current_record`, `is_month_end_record`,
  `is_week_end_record`, and `is_latest_record` dimensions (the guard and the
  named measures require them).
- **Deliberate design note — config lives in `cube.js`, not the cube YAML.**
  Per-cube anchor selection is resolved by cube-name lookup in
  `SNAPSHOT_ANCHOR_OVERRIDES` (keyed off the `cubePrefix` loop variable, the
  same pattern as the existing `SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS`
  cube-name-keyed config). This means a cube's default-anchor behavior is
  declared in `cube.js`, not in its own YAML — a mild separation-of-concerns
  trade-off, chosen for consistency with the existing snapshot config rather
  than a heavier metadata-driven refactor. Tracked in
  [#4155](https://github.com/TEAMSchools/teamster/issues/4155) for a future move
  to YAML so all of a cube's behavior is viewable in one place.

### Component 3 — view `student_enrollment_daily_summary`

`src/cube/model/views/students/student_enrollment_daily_summary.yml`. Summary
pattern (no direct identifiers): single `cube-access-student-data` policy,
`includes: "*"`. Use
[`student_attendance_summary.yml`](../../../src/cube/model/views/student_attendance/student_attendance_summary.yml)
as the structural template:

- Surfaces `count_students`, `count_students_served`, `count_students_active`,
  the three named state-count-date variants (`count_students_oct01` / `_oct15` /
  `_mar15`), and the four `is_*_record` anchor dimensions (under a `Filter`
  folder, as attendance does).
- **The view description must spell out the measure ladder** (all
  `count_distinct(student_key)`, all alumni-free because the year/date filter
  selects on the calendar day's school year, not student status — a prior-year
  graduate has no rows labeled the queried year). Verified 2026-06-09:
  - `count_students` + year filter → **enrolled as of each school's last
    occurred in-session day** (period-end-as-of-now): AY2025 → 10,374, AY2023 →
    9,630. Mixed as-of date across schools mid-year (Miami's last day Jun 4 vs
    Newark's Jun 9) — by design; each school as of its own last real day.
  - `count_students` + single `date_key` (e.g. 2025-10-01) → **~10,637 =
    enrolled _on that day_**, all schools as of the same calendar date.
  - `count_students_served` + year → **ever enrolled that year**: AY2025 →
    11,261, AY2023 → 10,381 (includes mid-year leavers). The topline
    `Total Enrollment` analog.
  - `count_students_active` + year → **~10,374 = active-status students**
    (status 0). Does **not** match topline by design; current-roster only.

  These answer different questions; the description must steer analysts to bare
  `count_students` (or a `date_key` pin) for point-in-time enrollment,
  `count_students_served` for "students we served," and `count_students_active`
  only for current active-roster questions (not historical point-in-time — see
  the Component 2 caveat).

- Time dimension via `join_path: student_enrollment_daily.dates`, `prefix: true`
  → `dates_*` members (day/week/month/quarter granularity).
- **Region and grade breakdowns come through join paths, not degenerate dims**:
  `join_path: student_enrollment_daily.locations.regions` (`prefix: true` →
  `regions_region_name`, `regions_state`) and
  `join_path: student_enrollment_daily.students` (`prefix: false`) for
  demographics. Resolves Open item C (region is not a fact column). Grade-level
  may stay a degenerate dim on the fact (`prefix: false`, bare `grade_level`) as
  attendance does.
- Folder grouping per the conformed-prefix convention: bare names for top-cube
  members, `<last-join-segment>_<member>` for `prefix: true` joins
  (`dates_date_day`, `regions_region_name`).

### Component 4 — view `student_enrollment_daily_detail`

`src/cube/model/views/students/student_enrollment_daily_detail.yml`. Row-level
drill-down to individual students (e.g. "who was enrolled on Oct 1?", roster
exports). Uses
[`student_enrollments_detail.yml`](../../../src/cube/model/views/students/student_enrollments_detail.yml)
as the structural template — same join paths and folders as the summary view,
plus the student-identifier members.

- Exposes the same measures and the `date` time dimension as the summary view,
  plus the PK `student_enrollment_daily_key` and the `students` identifier
  members (`student_key`, `full_name`, `birth_date`, `lea_student_identifier`,
  `state_student_identifier`, `enrollment_status`) and `student_enrollment_key`
  for stint-level joins.
- **Two-policy PII access** (per `src/cube/CLAUDE.md` detail-view rule):
  - `cube-access-student-data` — `includes: "*"` with `excludes:` listing every
    direct identifier (`full_name`, `birth_date`, `lea_student_identifier`,
    `state_student_identifier`, `district_student_identifier`,
    `salesforce_contact_id` — copy the existing `student_enrollments_detail`
    exclude list verbatim, adjusting for which of those members this view
    actually includes).
    - `cube-access-student-pii` — `includes: "*"`.
- Same folder structure as `student_enrollments_detail` (Enrollment / Status /
  Location / Student), plus a Date folder and the `Filter` anchor folder from
  the summary view.

This was previously scoped out as YAGNI; it is now a confirmed requirement
(drill-down to students), so it ships in this spec.

### Population and point-in-time semantics (the alumni question)

The fact is a **complete historical student-day record**, not a pre-filtered
"currently enrolled" table — exactly like
`int_extracts__student_enrollments_weeks`, which carries 467k enrolled-week rows
for graduates and 1.15M for withdrawn students across 14 years (verified
2026-06-09). Point-in-time-ness is a **query/measure concern (date filter +
anchors), never a row filter.**

This is the resolution to "won't old school calendars capture alumni?" — yes, at
the row level, and that is correct:

- `enroll_status` is **student-level, not per-stint** (see
  `src/dbt/kipptaf/CLAUDE.md`), so a 2025 graduate carries `enroll_status = 3`
  on all their historical stints. Of 42,940 status-3 stints, only 22,565 are
  null-dated placeholders; the other **20,375 have real dates** spanning every
  historical year and _will_ materialize as enrolled day-rows in old calendars.
- That is harmless because every count is date-pinned. "Enrollment on
  2025-10-01" filters `date_key = '2025-10-01'`; a 2025 grad's 2019 rows and a
  2019 grad's rows alike simply don't match. Alumni fall out **by date**, the
  same way they do in the weeks intermediate — which reconciles to topline
  despite containing all that history.
- **Do NOT add an `enroll_status` filter to scope alumni out of the table.** It
  would break the historical reconciliation (the weeks int doesn't filter, so
  the daily fact must not either) and is the wrong axis — point-in-time is a
  date question, not a status question. The only role-of-the-table filters are
  `insession = 1` (coverage decision) and the half-open date predicate (which
  correctly drops the null-dated placeholders, but is not the alumni mechanism).
- This is also why the base `count_students` must never be used unanchored:
  summing `is_enrolled` across all of history is precisely the alumni-inclusive
  footgun the anchors and date filters exist to prevent.

### Data flow

```text
int_powerschool__student_enrollment_union  (stints)   stg_powerschool__calendar_day
        │                                                      │  (insession = 1)
        └──────────────── stint ⋈ calendar-day ────────────────┘
                          │  (date-range join + anchor windows)
                          ▼
        fct_student_enrollment_daily         (new mart, Cube-readable)
                          │  sql_table
                          ▼
        student_enrollment_daily (cube)       (+ snapshot anchors in cube.js)
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   _daily_summary (view)        _daily_detail (view, PII-gated)
   (aggregate breakdowns)       (row-level student drill-down)
            └──────────── → MCP / Tableau / analysts
```

### Exposure

Add `fct_student_enrollment_daily` to `cube.yml`'s
`cube_semantic_layer.depends_on` (every Cube-consumed mart must appear there).

### Relationship to the existing weekly intermediate

`int_extracts__student_enrollments_weeks` is **not** touched — it has 17
downstream consumers (the entire topline weekly suite plus 4 Tableau extracts)
and stays as-is. The day-grain fact is independent; the topline reconciliation
(Open item D) compares the two for one week as a correctness check, not a
dependency.

## Resolved decisions

All five open items were closed against the warehouse on 2026-06-09; the
diagnostic figures are recorded inline so the plan inherits them.

- **A. Hash compatibility — RESOLVED (confirmed).** `_dbt_source_project` is
  present and non-null on all four districts in
  `int_powerschool__student_enrollment_union`. The reconstructed
  `student_enrollment_key`
  (`hash(student_number, _dbt_source_project, academic_year, entrydate)`) is
  unique across all 123,126 stints and matches `dim_student_enrollments` exactly
  for all 100,561 real-dated stints (the 22,565 unmatched are precisely the
  null-entrydate placeholders the fact drops). So the FK joins cleanly and the
  anchor windows partition by it — no fallback needed.
- **B. Graduate / historical stints — RESOLVED.** The half-open join drops the
  22,565 null-`entrydate` `enroll_status = 3` placeholders and retains the
  real-dated historical stints by design (see "Population and point-in-time
  semantics"). Alumni exclusion is a date-filter concern, never an
  `enroll_status` table filter. Plan-time check: assert 0 rows with NULL
  `entrydate` survive the join, and that a pinned recent-date count excludes
  prior-year grads.
- **C. Region scoping — RESOLVED.** Region resolves via the `locations` →
  `regions` join in the view, not a fact column. The mart is left **complete**
  (no Paterson filter, no year filter — see D) so it is reusable; scope happens
  in the view / query. Paterson is sparse (37K historical + 159K recent daily
  rows; its PowerSchool data effectively starts ~2024) but is not filtered out.
- **D. Reconciliation acceptance gate — TARGET ESTABLISHED.** Daily-fact
  `count_students` for the week containing 2025-10-01, filtered to that week's
  days, must equal the topline `is_enrolled_week` count from
  `int_extracts__student_enrollments_weeks` (verified 2026-06-09):

  | Region   | Expected enrolled |
  | -------- | ----------------- |
  | Camden   | 2,161             |
  | Miami    | 1,347             |
  | Newark   | 6,611             |
  | Paterson | 521               |
  | Total    | 10,640            |

  Also spot-check `count_students` at `date_key = date(academic_year, 10, 1)`
  against the upstream `is_enrolled_oct01` count for the same year.

- **E. Volume and materialization — RESOLVED.** Actual full-history volume is
  **~18.9M rows** (verified by joining stints to in-session calendar days,
  2026-06-09): Newark 13.0M (10.6M historical + 2.4M recent — 70% of the table),
  Camden 3.3M, Miami 1.4M, Paterson 0.2M. **Decision: full history, no year
  bound** (keeps the mart complete and makes historical point-in-time queries
  like "enrollment on 2019-10-01" answerable). At ~19M rows with `row_number()`
  windows, the mart **must be `materialized: table`** (override the marts `view`
  default) — a windowed view would re-expand on every Cube query. Benchmark the
  build time during implementation.

## Testing

- dbt:
  `uv run dbt build --select fct_student_enrollment_daily+ --project-dir src/dbt/kipptaf`
  (mart + its tests). Singular tests for the single-anchor invariants.
- Cube: validate compilation in Cube Cloud Dev Mode (manual; no local compile),
  and confirm the summary view returns counts matching the BigQuery
  point-in-time query for a fixed date and a fixed week.
- Detail view: confirm the two-policy PII gate — a `cube-access-student-data`
  (non-PII) context must not surface `full_name` / identifiers (a `/load` 500
  "hidden member" is the expected signal), while `cube-access-student-pii`
  resolves them; and that detail-view `count_students` for a fixed date equals
  the summary view's for the same filter.
- Reconciliation queries (Open item D) as the acceptance gate — both the
  one-week topline match and the Oct 1 day-exact match.

## Out of scope

- Changing the _semantics_ of the existing stint measure — it stays
  `count_distinct(student_enrollment_key)`; this spec only renames it to
  `count_enrollments` and documents it (see "Measure naming"), it does not alter
  what it counts.
- Touching `int_extracts__student_enrollments_weeks` or its 17 consumers.
- An every-calendar-day (incl. non-session) grain — in-session days only, per
  the coverage decision above.
