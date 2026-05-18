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
effective-date columns, and a Paterson + Miami leg pulling current-state values
from PowerSchool staging.

**Why no enrollment-year reconstruction**: `stg_powerschool__studentcorefields`
(the source of `spedlep` / `lep_status` for Paterson + Miami) is current-state
only — one row per student, no per-year history. Joining it across enrollment
years would propagate the current value backward as fake history. The honest
shape is one row per student carrying the current value, anchored to the
earliest observed enrollment.

### `dim_iep_status`

| Region          | Source model                                                                                            | Value columns                                                                                                  | Start date                                                                | End date              |
| --------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------- |
| Newark, Camden  | `int_edplan__njsmart_powerschool_union`                                                                 | `spedlep` (→ `iep_classification`), `special_education_code`, `special_education` (→ `special_education_name`) | `effective_date`                                                          | `effective_end_date`  |
| Paterson, Miami | `stg_powerschool__studentcorefields` joined to `base_powerschool__student_enrollments` for entry anchor | `spedlep` (→ `iep_classification`) only — code / name / placement null                                         | `min(entrydate)` per student from `base_powerschool__student_enrollments` | `'9999-12-31'` (open) |

Value-derivation in the Paterson + Miami leg uses the current
`stg_powerschool__studentcorefields.spedlep` coalesced to `'No IEP'`. `is_iep`
is derived as `iep_classification != 'No IEP'`.

### `dim_ell_status`

| Region          | Source model                                                                                            | Row emission                                                                                                        | Start date                                                                | End date                          |
| --------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------- |
| Newark, Camden  | `stg_powerschool__s_nj_stu_x`                                                                           | One row per non-null `lepbegindate` (plus one per non-null `lepbegindate2`) — every emitted row has `is_ell = true` | `lepbegindate`                                                            | `lependdate` (9999-12-31 if null) |
| Paterson, Miami | `stg_powerschool__studentcorefields` joined to `base_powerschool__student_enrollments` for entry anchor | One row per student where `lep_status = true`; no row when `lep_status` is false                                    | `min(entrydate)` per student from `base_powerschool__student_enrollments` | `'9999-12-31'` (open)             |

The secondary NJ range columns (`lepbegindate2`, `liependdate2`) generate
additional spans where populated.

**Known limitation**: `s_nj_stu_x` is a current-state table, not a versioned
one. Historical LEP entry/exit/re-entry transitions that have been overwritten
in the source are not recoverable. This is acceptable — exit/re-entry is not a
known real-world ELL pattern in our population. Document in the model's
`description:`.

### `dim_meal_eligibility_status`

| Region          | Source model                                                                        | Value column                                                      | Start date                                                                | End date               |
| --------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------------------- |
| Newark, Camden  | `stg_titan__person_data`                                                            | `eligibility_name` (Free / Reduced / Paid / Direct Certification) | `eligibility_start_date`                                                  | `eligibility_end_date` |
| Paterson, Miami | Most-recent `lunch_status` from `base_powerschool__student_enrollments` per student | `lunch_status`                                                    | `min(entrydate)` per student from `base_powerschool__student_enrollments` | `'9999-12-31'` (open)  |

`is_meal_eligible` derived as
`meal_eligibility IN ('Free', 'Reduced', 'Direct Certification')`. Paid / null /
invalid codes resolve to `false`.

For the Paterson + Miami leg, `lunch_status` is picked from the most recent
enrollment row per student (e.g. via `dbt_utils.deduplicate` partitioned by
student, ordered by `entrydate desc`) rather than the current PS staging
snapshot — `lunch_status` doesn't have a stable single-row analog like
`studentcorefields`.

## Dim SQL pattern

Each dim is a single mart-layer model — no `int_*` intermediate. All logic (NJ
leg + Paterson/Miami leg, island-collapse for NJ, current-state pick for
Paterson/Miami) lives inline. Marts/CLAUDE.md only requires `rpt_*` to buffer
external consumers from intermediates; mart dims building directly off staging

- existing intermediates is permitted.

```sql
-- dim_iep_status.sql (illustrative)
with
    nj_leg as (
        -- Native SCD2 from edplan. Collapse consecutive rows with unchanged
        -- (spedlep, special_education_code, special_education) into one span.
        select
            student_number,
            _dbt_source_project,
            spedlep as iep_classification,
            special_education_code,
            special_education as special_education_name,
            <placement_column> as special_education_placement,
            min(effective_date) as effective_date_start,
            coalesce(
                max(effective_end_date), date '9999-12-31'
            ) as effective_date_end,
        from {{ ref("int_edplan__njsmart_powerschool_union") }}
        group by <island_id, ...>      -- see "Island detection" below
    ),

    pm_leg as (
        -- Current-state pick: one row per student in Paterson/Miami, anchored
        -- to earliest enrollment entrydate, open-ended.
        select
            enr.student_number,
            enr._dbt_source_project,
            coalesce(scf.spedlep, 'No IEP') as iep_classification,
            cast(null as string) as special_education_code,
            cast(null as string) as special_education_name,
            cast(null as string) as special_education_placement,
            min(enr.entrydate) as effective_date_start,
            date '9999-12-31' as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(
                left_alias="enr", right_alias="scf"
            ) }}
        where enr.region in ('Paterson', 'Miami')
        group by 1, 2, 3, 4, 5, 6
    ),

    unioned as (
        select * from nj_leg
        union all
        select * from pm_leg
    )

select
    {{ dbt_utils.generate_surrogate_key([
        "student_number", "_dbt_source_project", "effective_date_start"
    ]) }} as iep_status_key,
    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,
    iep_classification != 'No IEP' as is_iep,
    iep_classification,
    special_education_code,
    special_education_name,
    special_education_placement,
    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
```

`dim_ell_status` and `dim_meal_eligibility_status` follow the same shape with
their respective upstreams and value columns.

### Island detection (NJ legs only)

The NJ legs (`int_edplan__njsmart_powerschool_union`,
`stg_powerschool__s_nj_stu_x`, `stg_titan__person_data`) collapse consecutive
rows where the tracked value is unchanged into a single span. Gap-and-island
pattern:

```sql
with
    flagged as (
        select
            *,
            if(
                <value_column> = lag(<value_column>) over (
                    partition by student_number, _dbt_source_project
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
                partition by student_number, _dbt_source_project
                order by <start_date_column>
            ) as island_id,
        from flagged
    )

select
    student_number,
    _dbt_source_project,
    <value_column>,
    min(<start_date_column>) as effective_date_start,
    coalesce(max(<end_date_column>), date '9999-12-31') as effective_date_end,
from islanded
group by 1, 2, 3, island_id
```

For multi-column value tracking (IEP: `spedlep` + `special_education_code` +
`special_education_name`), the lag comparison uses `format("%T|%T|%T", ...)` for
NULL-safe concatenation per `src/dbt/CLAUDE.md`.

## `_dbt_source_project` promotion (additive upstream edits)

Per `marts/CLAUDE.md` and
[#3142](https://github.com/TEAMSchools/teamster/issues/3142), all union models
feeding this work must materialize `_dbt_source_project` — downstream consumers
(these dims) join and hash on the materialized column, not re-derive it from
`_dbt_source_relation`.

Status before this work:

| Model                                         | Materializes `_dbt_source_project`?    |
| --------------------------------------------- | -------------------------------------- |
| `base_powerschool__student_enrollments`       | ✓ (alongside legacy `code_location`)   |
| `int_edplan__njsmart_powerschool_union`       | ✗ — add as additive edit               |
| `stg_powerschool__s_nj_stu_x` (kipptaf union) | ✗ — add as additive edit               |
| `stg_titan__person_data` (kipptaf union)      | ✗ — add as additive edit               |
| `stg_powerschool__studentcorefields`          | verify; add as additive edit if absent |

Add:

```sql
regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
```

immediately after the `union_relations` CTE in each model. Update their
`properties/*.yml` to add the column to the contract. Do not drop
`code_location` from `base_powerschool__student_enrollments` — full
`code_location` deprecation across consumers is out of scope and will land with
the rest of #3142.

## Dim shapes (PK, columns, tests)

### `dim_iep_status`

```text
iep_status_key                = generate_surrogate_key(student_number, _dbt_source_project, effective_date_start)   -- PK
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
ell_status_key                = generate_surrogate_key(student_number, _dbt_source_project, effective_date_start)   -- PK
student_key                   FK → dim_students
is_ell                        BOOL
effective_date_start_key      DATE   FK → dim_dates
effective_date_end_key        DATE   FK → dim_dates
is_current                    BOOL
```

### `dim_meal_eligibility_status`

```text
meal_eligibility_status_key   = generate_surrogate_key(student_number, _dbt_source_project, effective_date_start)   -- PK
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
- Singular test: no overlapping spans per student × `_dbt_source_project`

### Contracts and constraints

Inherited from `marts/` directory config: `contract: enforced: true`,
`materialized: view`. PK/FK `constraints:` blocks include
`warn_unsupported: false` per marts/CLAUDE.md.

### Strict-chain traversal

These dims FK only to `dim_students` and `dim_dates`. No `region_key`,
`location_key`, or shortcut FKs to deeper dims — consumers traverse the chain
through `dim_students` to reach location / region context.

### `dim_dates` sentinel row

The `'9999-12-31'` end-date sentinel requires a matching row in `dim_dates` for
the `effective_date_end_key` relationships test to pass. Verify the row exists
before merge; if missing, extend the `dim_dates` generator to include it
(additive upstream edit).

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
  Paterson keeps separate spans per `_dbt_source_project` rather than unifying).
  Consumers filter by date and source as needed.

## Hash-change posture

Three new dims with new PKs — no existing hashes affected. `is_ell` removal from
`dim_students` doesn't affect its PK (`student_key` hashes `student_number`
only).

## Pre-merge checks

Per marts/CLAUDE.md "Pre-merge checklist (marts PRs)":

- Scan the three new `dim_*` files for diamond paths (none expected — FKs go
  only to `dim_students` + `dim_dates`).
- Scan all three new files for column-naming rubric violations (R1–R10). Hot
  spots specific to this work: `iep_classification` (R2 / R7 — no bare `spedlep`
  or `lep`), `special_education_code` + `special_education_name` (degenerate-dim
  code+name pairing), `meal_eligibility` (no `_status` suffix), `is_*` booleans
  (R3).
- Confirm `_dbt_source_project` is materialized on all four upstream union
  models touched by this work and that downstream consumers of those models
  still parse (additive contract change only).
- Confirm `dim_iep_status`, `dim_ell_status`, `dim_meal_eligibility_status`
  appear in `cube.yml`'s `cube_semantic_layer.depends_on`.
- Pull marts-model warnings from the latest CI run
  (`mcp__dbt__get_job_run_error` with `warning_only=true`); bucket and file
  follow-ups per marts/CLAUDE.md "Filing follow-up issues from marts work"
  before the final PR comment.
- Scan project board [#4](https://github.com/orgs/TEAMSchools/projects/4) for
  bonus issues incidentally resolved; close them in the PR.

## Implementation order

1. Promote `_dbt_source_project` to the upstream union models that need it
   (`int_edplan__njsmart_powerschool_union`, `stg_powerschool__s_nj_stu_x`
   kipptaf union, `stg_titan__person_data` kipptaf union, and
   `stg_powerschool__studentcorefields` kipptaf union if absent). Update each
   model's `properties/*.yml` contract. Additive only — no `code_location`
   removal in this PR.
2. Verify `dim_dates` has a `'9999-12-31'` row; extend the generator if not.
3. Build the three `dim_*` models (each a single mart-layer file containing NJ
   leg + Paterson/Miami leg + island-collapse). Write `properties/*.yml` with
   descriptions, constraints (`warn_unsupported: false`), and tests.
4. Remove `is_ell` from `dim_students` SQL + YAML.
5. Add the three dim names to `cube.yml` `cube_semantic_layer.depends_on`.
6. Verify with
   `uv run dbt build --select dim_iep_status+ dim_ell_status+ dim_meal_eligibility_status+`
   against the relevant project (worktree-scoped `--project-dir`).
