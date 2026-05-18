# SCD2 dims for IEP, ELL, and meal-eligibility status

Tracking issue: [#3960](https://github.com/TEAMSchools/teamster/issues/3960).

## Problem

`has_iep` and `meal_eligibility_status` were dropped from `dim_students` in
`af0c2bf22` (closes #3723) with the rationale that they are enrollment
attributes, not student attributes. `is_ell` remained but was simplified to the
current PowerSchool `studentcorefields.lep_status` flag, dropping the prior
enrollment-date-window logic.

Net effect at the mart layer:

- **IEP** — not surfaced at all. `spedlep`, `special_education_code`,
  `special_education_placement` live only at enrollment grain in
  `base_powerschool__student_enrollments` and downstream `int_extracts__*`.
- **ELL** — surfaced as a single point-in-time boolean on `dim_students`, with
  no date-bound logic. Cannot answer "was student X ELL on date Y?"
- **Meal eligibility** — not surfaced at all.

These three attributes are date-bound by nature. The right shape is one
SCD2-style dimension per attribute, with effective-date spans per student.

## Solution

Add three new mart dimensions under `src/dbt/kipptaf/models/marts/dimensions/`:

- `dim_iep_status`
- `dim_ell_status`
- `dim_meal_eligibility_status`

Each dim carries one row per (student × effective span) for its attribute.
Active rows use `'9999-12-31'` as the end-date sentinel, matching the project's
snapshot convention.

### Row semantics

The dims are **inclusion-based**: a row exists only where the source has a span
to report. Students with no row covering date Y are treated as "unknown / not
applicable" — consumers default to `false` / `'No IEP'` / `null` accordingly:

```sql
coalesce(
    (
        select is_iep
        from {{ ref("dim_iep_status") }}
        where student_key = s.student_key
            and target_date between effective_date_start_key
                                and effective_date_end_key
    ),
    false
) as is_iep_on_date
```

This is why the NJ legs may emit only positive spans (edplan only sends students
with IEPs; `s_nj_stu_x` only carries non-null `lepbegindate` for students with
LEP records) while the Paterson + Miami reconstruction legs emit both true and
false spans (every enrollment-year row contributes). The asymmetry is acceptable
under the coalesce-default semantics.

`is_ell` is removed from `dim_students` as part of this work. Boolean rollups
(`is_iep`, `is_ell`, `is_meal_eligible`) live on the new dims as derived
attributes — not on `dim_students`.

## Source map

Each dim has two legs: an NJ leg using a native upstream model with
effective-date columns, and a Paterson + Miami leg using enrollment-year
reconstruction from `base_powerschool__student_enrollments`. The two legs union
into the final dim.

### `dim_iep_status`

| Region          | Source model                            | Value columns                                                                                                  | Start date       | End date             |
| --------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------- | -------------------- |
| Newark, Camden  | `int_edplan__njsmart_powerschool_union` | `spedlep` (→ `iep_classification`), `special_education_code`, `special_education` (→ `special_education_name`) | `effective_date` | `effective_end_date` |
| Paterson, Miami | `base_powerschool__student_enrollments` | `spedlep` (→ `iep_classification`) only — code / name / placement null                                         | `entrydate`      | `exitdate`           |

Value-derivation in the Paterson + Miami leg mirrors today's `spedlep` chain in
`base_powerschool__student_enrollments`: `coalesce(ar.spedlep, 'No IEP')` —
`is_iep` is derived as `iep_classification != 'No IEP'`.

### `dim_ell_status`

| Region          | Source model                            | Row emission                                                                                                        | Start date     | End date                          |
| --------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------- | --------------------------------- |
| Newark, Camden  | `stg_powerschool__s_nj_stu_x`           | One row per non-null `lepbegindate` (plus one per non-null `lepbegindate2`) — every emitted row has `is_ell = true` | `lepbegindate` | `lependdate` (9999-12-31 if null) |
| Paterson, Miami | `base_powerschool__student_enrollments` | Enrollment-year island-collapse on `lep_status` (emits both true and false spans)                                   | `entrydate`    | `exitdate`                        |

The secondary NJ range columns (`lepbegindate2`, `liependdate2`) generate
additional spans where populated.

**Known limitation**: `s_nj_stu_x` is a current-state table, not a versioned
one. Historical LEP entry/exit/re-entry transitions that have been overwritten
in the source are not recoverable. This is acceptable — exit/re-entry is not a
known real-world ELL pattern in our population. Document in the model's
`description:`.

### `dim_meal_eligibility_status`

| Region          | Source model                            | Value column                                                      | Start date               | End date               |
| --------------- | --------------------------------------- | ----------------------------------------------------------------- | ------------------------ | ---------------------- |
| Newark, Camden  | `stg_titan__person_data`                | `eligibility_name` (Free / Reduced / Paid / Direct Certification) | `eligibility_start_date` | `eligibility_end_date` |
| Paterson, Miami | `base_powerschool__student_enrollments` | `lunch_status`                                                    | `entrydate`              | `exitdate`             |

`is_meal_eligible` derived as
`meal_eligibility IN ('Free', 'Reduced', 'Direct Certification')`. Paid / null /
invalid codes resolve to `false`.

## Build pattern

Each `dim_*` model wraps a single `int_*` model that builds the unioned SCD2
result. The intermediates live under
`src/dbt/kipptaf/models/students/intermediate/`:

- `int_students__iep_status_history`
- `int_students__ell_status_history`
- `int_students__meal_eligibility_status_history`

### Intermediate shape

```sql
with
    nj_leg as (
        -- Source the native effective-date columns from the upstream model.
        -- Collapse consecutive rows where the tracked values are unchanged
        -- into a single span via lag()-based island detection.
        select
            student_number,
            code_location,
            <value_columns>,
            <first effective_date_start in island> as effective_date_start,
            <last  effective_date_end   in island> as effective_date_end,
        from {{ ref("<nj_upstream>") }}
        ...
    ),

    reconstruction_leg as (
        -- Pull yearly enrollment rows for regions without a native upstream.
        -- Same island-collapse pattern on (entrydate, exitdate) bounds.
        select
            student_number,
            code_location,
            <value_columns>,
            <first entrydate in island> as effective_date_start,
            <last  exitdate  in island> as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }}
        where region in ('Paterson', 'Miami')
        ...
    )

select * from nj_leg
union all
select * from reconstruction_leg
```

### Island detection

Standard gap-and-island pattern:

```sql
with
    flagged as (
        select
            *,
            if(
                <value_column> = lag(<value_column>) over (
                    partition by student_number, code_location
                    order by <start_date_column>
                ),
                0,
                1
            ) as is_island_start,
        from <source>
    ),

    islanded as (
        select
            *,
            sum(is_island_start) over (
                partition by student_number, code_location
                order by <start_date_column>
            ) as island_id,
        from flagged
    )

select
    student_number,
    code_location,
    <value_column>,
    min(<start_date_column>) as effective_date_start,
    coalesce(max(<end_date_column>), date '9999-12-31') as effective_date_end,
from islanded
group by all  -- TODO: enumerate; see SQL conventions
```

(Final implementation enumerates GROUP BY columns per project SQL conventions —
`GROUP BY ALL` is not allowed.)

For multi-column value tracking (IEP: `spedlep` + `special_education_code`

- `special_education_name`), the lag comparison uses `format("%T|%T|%T", ...)`
  to handle null safety per the `src/dbt/CLAUDE.md` cross-district-queries
  NULL-safe-concat note.

### `code_location` materialization

`base_powerschool__student_enrollments` already materializes `code_location`
(per #3142). Confirm `int_edplan__njsmart_powerschool_union` and
`stg_titan__person_data` do as well; if not, this is an additive upstream edit
included in scope.

## Dim shapes (PK, columns, tests)

### `dim_iep_status`

```text
iep_status_key                = generate_surrogate_key(student_number, code_location, effective_date_start)   -- PK
student_key                   = generate_surrogate_key(student_number)                                          -- FK → dim_students
is_iep                        BOOL
iep_classification            STRING — degenerate
special_education_code        STRING — degenerate, NJ-only (paired with _name)
special_education_name        STRING — degenerate, NJ-only (paired with _code)
special_education_placement   STRING — degenerate, NJ-only
effective_date_start_key      DATE   — FK → dim_dates
effective_date_end_key        DATE   — FK → dim_dates (9999-12-31 = active)
is_current                    BOOL   (effective_date_end_key = '9999-12-31')
```

### `dim_ell_status`

```text
ell_status_key                = generate_surrogate_key(student_number, code_location, effective_date_start)   -- PK
student_key                   FK → dim_students
is_ell                        BOOL
effective_date_start_key      DATE   FK → dim_dates
effective_date_end_key        DATE   FK → dim_dates
is_current                    BOOL
```

### `dim_meal_eligibility_status`

```text
meal_eligibility_status_key   = generate_surrogate_key(student_number, code_location, effective_date_start)   -- PK
student_key                   FK → dim_students
meal_eligibility              STRING — degenerate
is_meal_eligible              BOOL
effective_date_start_key      DATE   FK → dim_dates
effective_date_end_key        DATE   FK → dim_dates
is_current                    BOOL
```

### Tests

Each dim:

- `unique` on PK
- `not_null` on PK, `student_key`, `effective_date_start_key`,
  `effective_date_end_key`, `is_current`, and the boolean derived attribute
  (`is_iep` / `is_ell` / `is_meal_eligible`)
- `relationships` from `student_key` to `dim_students.student_key`
- `relationships` from `effective_date_start_key` / `effective_date_end_key` to
  `dim_dates.date_key`
- Singular test: no overlapping spans per student × code_location

### Contracts and constraints

Inherited from `marts/` directory config: `contract: enforced: true`,
`materialized: view`. PK/FK `constraints:` blocks include
`warn_unsupported: false` per marts/CLAUDE.md.

## Cube exposure update

Add the three new dim names to `cube.yml`'s `cube_semantic_layer.depends_on`
list. No Cube view files in this PR — that's a follow-up.

## `dim_students` change

Remove `is_ell` from `dim_students` and its `properties/dim_students.yml`. No
other column changes. Consumers shift to `dim_ell_status` filtered by date.

## Out of scope

- Cube view files (`{iep,ell,meal_eligibility}_{detail,summary}.yml`) —
  follow-up issue.
- `fct_iep_meetings` (per-meeting events: initial / annual review / parent
  consent dates) — current consumers (`rpt_tableau__ops_dashboard`,
  `int_extracts__student_enrollments_subjects_weeks`) are pass-through display,
  no calculations on the values. File a follow-up if/when a calculation requires
  them.
- `dim_504_status`, `dim_gifted_status` — same pattern, separate issues.
- Cross-district student transfer reconciliation (a student moving Newark →
  Paterson keeps separate spans per `code_location` rather than unifying).
  Consumers filter by date and source as needed.

## Hash-change posture

Three new dims with new PKs — no existing hashes affected. `is_ell` removal from
`dim_students` doesn't affect its PK (`student_key` hashes `student_number`
only).

## Implementation order

1. Confirm `int_edplan__njsmart_powerschool_union` and `stg_titan__person_data`
   materialize `code_location`. Add if missing (additive upstream edit).
2. Build the three `int_*` intermediates with island-collapse logic.
3. Build the three `dim_*` mart wrappers + YAML properties.
4. Remove `is_ell` from `dim_students` SQL + YAML.
5. Add the three dim names to `cube.yml` `cube_semantic_layer.depends_on`.
6. Verify with
   `uv run dbt build --select dim_iep_status+ dim_ell_status+ dim_meal_eligibility_status+`
   against the relevant project.
