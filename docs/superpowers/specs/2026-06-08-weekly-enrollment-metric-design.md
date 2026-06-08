# Point-in-time weekly student enrollment metric

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
match the topline numbers. Today they cannot get that from Cube.

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
  enrolled in the specific week measured.

## Why not just join the existing cube to a date scaffold

Cube cannot expand the stint table into a weekly grain on the fly:

- Cube has **no non-equi / BETWEEN join** (`src/cube/CLAUDE.md`). A
  `date BETWEEN entry_date AND exit_date` join is not expressible.
- A Cube dimension cannot reference a measure; "classify an aggregate by a
  data-driven range" is explicitly unsupported.
- A `many_to_one` BETWEEN from stint to dates would fan a stint into N週 rows
  and silently mis-aggregate, because Cube's fan-trap protection trusts the
  declared relationship. (Fan-out: N week-rows per stint.)

The weekly expansion already exists upstream:
`int_extracts__student_enrollments_weeks` is one row per
`(_dbt_source_relation, student_number, week_start_monday)`, with
`is_enrolled_week`. The only missing piece is a **mart** that exposes this
intermediate to Cube (Cube reads `kipptaf_marts.*` only; an intermediate cannot
be a Cube source, and a mart must buffer external consumers from intermediate
schema drift).

## Validation gotcha (must be designed around)

`is_current_week_mon_sun` flags **3 weeks**, not one (validated 2026-06-08:
`2026-06-01`, `2026-06-08`, `2026-06-15`). A naive
`countif(is_enrolled_week AND is_current_week_mon_sun)` over-counts the
point-in-time headcount ~2–3×. The mart must expose a **true
single-row-per-period anchor** — the attendance pattern's `is_latest_record` /
`is_week_end_record` / `is_month_end_record` — not this flag.

The source grain is unique on
`(_dbt_source_relation, student_number, week_start_monday)` (verified: 0
violations AY2025), so once a single week is isolated,
`countif(is_enrolled_week)` equals `count(distinct student)`.

## Design

### Component 1 — mart `fct_student_enrollment_weeks`

A thin fact view in `src/dbt/kipptaf/models/marts/facts/` over
`int_extracts__student_enrollments_weeks`. It projects the existing weekly grain
and adds the snapshot anchors. No new business logic — the enrollment expansion
stays upstream.

Grain: one row per
`(student_number, _dbt_source_project, academic_year, week_start_monday)`.

Columns:

- `student_enrollment_week_key` — PK,
  `generate_surrogate_key([student_number, _dbt_source_project, academic_year, week_start_monday])`.
- `student_enrollment_key` — FK to `dim_student_enrollments`, hashed identically
  to that dim (`student_number, _dbt_source_project, academic_year, entrydate`)
  so the new fact joins the existing enrollment dim. **Open item A** (below):
  confirm the weeks model carries a single `entrydate` per row matching the
  dim's hash inputs.
- `student_key` — FK to `students` (`dim_students`).
- `location_key` — FK to `locations` (`dim_locations`), via `schoolid` →
  `stg_powerschool__schools` like `dim_student_enrollments` does.
- `week_start_date_key` — DATE = `week_start_monday`, FK to `dim_dates`.
- `week_end_date_key` — DATE = `week_end_sunday`.
- `academic_year`, `grade_level`, `region` (degenerate dims for filtering /
  parity with topline's Paterson handling — see Open item C).
- `is_enrolled_week` — INT64 0/1 (per marts R3, countable flag on a fact).
- Anchor flags (INT64 0/1, exactly one row true per student per period):
  - `is_latest_record` — the max `week_start_monday` per
    `(student, academic_year)` that has an enrolled or recorded row (single-row,
    unlike `is_current_week_mon_sun`).
  - `is_week_end_record` — every row is a week, so this equals 1 for all rows (a
    week _is_ the week-grain period). Retained for cube.js anchor-injection
    symmetry. **Open item B**: confirm whether week granularity needs an anchor
    at all, or whether only month/quarter roll-ups do.
  - `is_month_end_record` — the last week whose `week_end_sunday` falls in a
    given calendar month, per `(student, academic_year, month)`.
- `is_current_week` — pass through `is_current_week_mon_sun` **unchanged but
  renamed**, with a description warning it spans multiple weeks; not an anchor.

Tests: `dbt_utils.unique_combination_of_columns` on the PK hash inputs (or
`unique` on `student_enrollment_week_key`); `relationships` on each FK; the
single-row invariant on anchors enforced by a singular test (`tests/test_*.sql`)
— exactly one `is_latest_record` per `(student, academic_year)`.

### Component 2 — cube `student_enrollment_weeks`

`src/cube/model/cubes/students/student_enrollment_weeks.yml`, `public: false`,
`sql_table: kipptaf_marts.fct_student_enrollment_weeks`.

- Dimensions: PK, the three FKs (`relationship: many_to_one` joins to
  `students`, `locations`, `student_enrollments`), `week_start_date` /
  `week_end_date` (cast to TIMESTAMP per cube time-dimension rule),
  `academic_year`, `grade_level`, `region`, and the three `is_*_record`
  anchors + `is_enrolled_week`.
- Measure `count_students`: `sum(is_enrolled_week)` (type `sum`) — the topline
  methodology. **Semantics differ from the stint cube's `count_students`**: this
  is a per-period sum, valid only when the query isolates a single period via an
  anchor (`is_latest_record` etc.). Without an anchor, summing across weeks
  yields enrolled-student-weeks, not a headcount — which is exactly why the
  snapshot guard in cube.js is mandatory, not optional, for this measure. The
  shared name is intentional (reads the same in BI) but the two measures are not
  interchangeable; the view description must state this.
- A date join to `dates` on `week_start_date_key` for week/month/quarter
  granularity in the view.

`cube.js` wiring:

- Append `"student_enrollment_weeks"` to `STUDENT_CUBES` (student-data gating).
- Append `"student_enrollment_weeks"` to `SNAPSHOT_CUBES`.
- Add `"enrolled"` (or the exact measure-name stem) to `SNAPSHOT_MEASURE_STEMS`
  so the anchor guard injects `is_latest_record` / `is_month_end_record` /
  `is_week_end_record` by query granularity.
- The cube must expose all three `is_*_record` dimensions (the guard requires
  them).

### Component 3 — view `student_enrollment_weeks_summary`

`src/cube/model/views/students/student_enrollment_weeks_summary.yml`. Summary
pattern (no direct identifiers): single `cube-access-student-data` policy,
`includes: "*"`. Surfaces `count_students`, the week/month/quarter time
dimension (prefixed conformed `dates`), and demographic / region / grade
breakdowns. Folder grouping per the conformed-prefix convention established in
the rename work.

A `*_detail` view is **out of scope** for this spec (YAGNI — topline
reconciliation is aggregate; add later if row-level drill-down is needed).

### Data flow

```text
int_extracts__student_enrollments_weeks   (existing intermediate, weekly grain)
        │  (thin projection + anchor flags)
        ▼
fct_student_enrollment_weeks              (new mart, Cube-readable)
        │  sql_table
        ▼
student_enrollment_weeks (cube)           (+ snapshot anchors in cube.js)
        │
        ▼
student_enrollment_weeks_summary (view)   → MCP / Tableau / analysts
```

### Exposure

Add `fct_student_enrollment_weeks` to `cube.yml`'s
`cube_semantic_layer.depends_on` (every Cube-consumed mart must appear there).

## Open items to resolve during planning

- **A. Hash compatibility.** Confirm `int_extracts__student_enrollments_weeks`
  exposes the columns to hash `student_enrollment_key` identically to
  `dim_student_enrollments`
  (`student_number, _dbt_source_project, academic_year, entrydate`). The weeks
  model carries `entrydate`; verify `_dbt_source_project` is derivable (it
  carries `_dbt_source_relation`). If the hash cannot match, the FK to
  `dim_student_enrollments` is dropped and the fact links to `students` only.
- **B. Week anchor necessity.** Decide whether `is_week_end_record` is
  meaningful at week grain (likely a no-op = always 1) or whether the guard
  should only fire for month/quarter roll-ups. Mirror whatever attendance does.
- **C. Paterson + recent-year scoping.** Topline excludes Paterson and filters
  `academic_year >= current - 1` at the metric layer. Decide whether the mart
  filters these or leaves them in and lets the view/query scope. Recommendation:
  leave the mart complete; scope in the view or via query filters, so the mart
  is reusable.
- **D. Reconcile against topline exactly.** Before merge, validate the new
  `count_students` for one isolated week equals topline's `Total Enrollment` for
  the same week and region, accounting for the `is_current_week` triple-flag.

## Testing

- dbt:
  `uv run dbt build --select fct_student_enrollment_weeks+ --project-dir src/dbt/kipptaf`
  (mart + its tests). Singular test for the single-anchor invariant.
- Cube: validate compilation in Cube Cloud Dev Mode (manual; no local compile),
  and confirm the summary view returns counts matching the BigQuery
  point-in-time query for a fixed week.
- Reconciliation query (Open item D) as the acceptance gate.

## Out of scope

- Changing the existing `student_enrollments.count_students` measure (it remains
  a valid stint count).
- A row-level `*_detail` weekly view.
- Fixing `is_current_week_mon_sun` upstream (documented as a gotcha; the mart
  works around it with real anchors).
