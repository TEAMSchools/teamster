# Point-in-time daily student enrollment metric

Issue: [#4138](https://github.com/TEAMSchools/teamster/issues/4138)

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
- `academic_year`, `grade_level` (degenerate dims for filtering). Region is
  **not** a fact column — it resolves through the `locations` → `regions` join
  in the view (Component 3).
- `is_enrolled` — INT64 1 for every row (each row is an enrolled in-session day;
  per marts R3, a countable flag). Retained as the summable measure base so
  `sum(is_enrolled)` reads naturally; could also be `membership_value` if a
  partial-membership distinction is ever needed (not now).
- Anchor flags (INT64 0/1) — the same three `fct_student_attendance_daily`
  exposes, computed with identical `row_number()` windows partitioned by
  `student_enrollment_key`:
  - `is_latest_record` —
    `row_number() over (partition by student_enrollment_key order by date_key desc) = 1`.
    The student's most recent in-session day in the stint; drives `_year_end`
    measures (attendance filters `_year_end` on `is_latest_record`, not a
    separate flag — mirror that).
  - `is_month_end_record` —
    `row_number() over (partition by student_enrollment_key, date_trunc(date_key, month) order by date_key desc) = 1`.
    The last in-session day per student-month.
  - `is_week_end_record` — same window with
    `date_trunc(date_key, week(monday))`. The last in-session day per
    student-week. **At day grain this is a real anchor** (the no-op concern that
    dogged the weekly design is gone — a week now has multiple day-rows, exactly
    one of which is the week-end).

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
- Measures follow the **named period-end pattern** that `student_attendance`
  uses (`count_truants_year_end` / `_month_end` / `_week_end`) — base measure
  unanchored, explicit variants carrying the anchor filter, rather than relying
  on `SNAPSHOT_MEASURE_STEMS` substring injection:
  - `count_students`: `sum(is_enrolled)` (type `sum`). Base measure, no anchor
    filter. This is the honest per-period student headcount (the stint cube's
    counter is renamed `count_enrollments` — see "Measure naming" above — so
    `count_students` is unambiguous). Valid only when the query isolates a
    single period (via a `date` filter — e.g. Oct 1 — or one of the `_*_end`
    variants). Summed across days unanchored it yields enrolled-student-days,
    not a headcount; the view description must say so.
  - `count_students_year_end`: `sum(is_enrolled)` with measure filter
    `{CUBE}.is_latest_record = true`. Safe for year-over-year without an anchor
    filter — mirrors `count_truants_year_end`.
  - `count_students_month_end`: filter `{CUBE}.is_month_end_record = true`. Use
    with `timeDimensions` granularity `month`.
  - `count_students_week_end`: filter `{CUBE}.is_week_end_record = true`. Use
    with granularity `week`.
- A date join to `dates` on `date_key` for day/week/month/quarter granularity in
  the view. The day-grain `date` dimension is itself the answer to "enrollment
  on a specific date" — a single-date filter on `count_students` needs no
  anchor.

`cube.js` wiring:

- **No domain-gating edit needed.** Access gating is prefix-derived
  (`isStudentMember = (m) => m.startsWith("student")`,
  [cube.js](../../../src/cube/cube.js)); the cube name
  `student_enrollment_daily` is gated automatically. The old `STUDENT_CUBES`
  array no longer exists.
- Append `"student_enrollment_daily"` to `SNAPSHOT_CUBES`.
- Leave the base `count_students` **out** of `SNAPSHOT_MEASURE_STEMS`: the named
  `_year_end` / `_month_end` / `_week_end` measures carry their anchors
  explicitly (the `SNAPSHOT_SELF_ANCHORED_SUFFIXES` convention in
  [cube.js](../../../src/cube/cube.js) recognizes these suffixes and skips
  re-injecting), and the base measure's intended unanchored use is a single-date
  filter. This matches how attendance leaves `avg_daily_attendance` unanchored.
- The cube must expose all three `is_*_record` dimensions (the guard and the
  named measures both require them).

### Component 3 — view `student_enrollment_daily_summary`

`src/cube/model/views/students/student_enrollment_daily_summary.yml`. Summary
pattern (no direct identifiers): single `cube-access-student-data` policy,
`includes: "*"`. Use
[`student_attendance_summary.yml`](../../../src/cube/model/views/student_attendance/student_attendance_summary.yml)
as the structural template:

- Surfaces `count_students` + the three named period-end variants
  (`count_students_year_end` / `_month_end` / `_week_end`) and the three
  `is_*_record` anchors (under a `Filter` folder, as attendance does).
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

A `*_detail` view is **out of scope** for this spec (YAGNI — topline
reconciliation is aggregate; add later if row-level drill-down is needed).

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
                          ▼
        student_enrollment_daily_summary (view)   → MCP / Tableau / analysts
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

## Open items to resolve during planning

- **A. Hash compatibility (load-bearing twice).** `student_enrollment_key` is
  both the FK to `dim_student_enrollments` and the partition key for the three
  anchor windows. Confirm it reconstructs identically to the dim
  (`student_number, _dbt_source_project, academic_year, entrydate`) from the
  stint side of the join. The stint source carries all four; verify
  `_dbt_source_project` is materialized (or derive via `extract_code_location`).
  If the hash cannot match, the FK is dropped and the windows partition by
  `(student_number, _dbt_source_project, academic_year)` instead — but that
  collapses multi-stint students in a way the per-stint key would not, so prefer
  fixing the hash.
- **B. Graduate / historical stints (resolved — see "Population and
  point-in-time semantics").** The half-open join drops the 22,565 null-dated
  `enroll_status = 3` placeholders (NULL fails the predicate), but **retains**
  the 20,375 real-dated historical grad stints — by design. Alumni exclusion is
  a date-filter concern, not a table filter; do not add an `enroll_status`
  predicate. The only planning task here is to confirm the null-dated
  placeholders do in fact drop (verify 0 rows with NULL `entrydate` survive the
  join) and that the count at a pinned recent date excludes prior-year grads.
- **C. Region / recent-year scoping.** Region resolves via the `locations` →
  `regions` join in the view (not a fact column). **Still open:** whether the
  _mart_ filters out Paterson and applies `academic_year >= current - 1`, or
  leaves the data complete and scopes in the view / query. Recommendation: leave
  the mart complete and scope downstream, so the mart is reusable.
- **D. Reconcile against topline exactly.** Before merge, validate that
  `count_students` filtered to the days of one week equals topline's
  `Total Enrollment` for the same week and region (from
  `int_extracts__student_enrollments_weeks`). Also spot-check `count_students`
  at `date_key = date(academic_year, 10, 1)` against the upstream
  `is_enrolled_oct01` count for the same year.
- **E. Row volume and history bound.** Full history ≈ **16M rows** (~11.6M
  pre-2024 + ~4.1M AY2024+, estimated 2026-06-09 from enrolled-week rows × ~5
  in-session days). That is `fct_student_attendance_daily` scale, so it is
  tolerable as a table — but the marts default is `view`, and a 16M-row windowed
  fact almost certainly warrants `materialized: table` (decide + benchmark).
  This is also where the recent-year question from item C bites hardest: if no
  consumer needs pre-2024 day-grain enrollment, an
  `academic_year >= current - N` bound in the mart roughly quarters the table.
  Decide the history bound and materialization together; if bounding,
  `log`/document the dropped years so it isn't mistaken for complete coverage.

## Testing

- dbt:
  `uv run dbt build --select fct_student_enrollment_daily+ --project-dir src/dbt/kipptaf`
  (mart + its tests). Singular tests for the single-anchor invariants.
- Cube: validate compilation in Cube Cloud Dev Mode (manual; no local compile),
  and confirm the summary view returns counts matching the BigQuery
  point-in-time query for a fixed date and a fixed week.
- Reconciliation queries (Open item D) as the acceptance gate — both the
  one-week topline match and the Oct 1 day-exact match.

## Out of scope

- Changing the _semantics_ of the existing stint measure — it stays
  `count_distinct(student_enrollment_key)`; this spec only renames it to
  `count_enrollments` and documents it (see "Measure naming"), it does not alter
  what it counts.
- Touching `int_extracts__student_enrollments_weeks` or its 17 consumers.
- A row-level `*_detail` daily view.
- An every-calendar-day (incl. non-session) grain — in-session days only, per
  the coverage decision above.
