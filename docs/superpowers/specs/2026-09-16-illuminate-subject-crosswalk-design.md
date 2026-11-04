# Vendor-to-Illuminate subject crosswalk

Refs [#5340](https://github.com/TEAMSchools/teamster/issues/5340).

## Problem

`illuminate_subject` translates a vendor's or a state's own subject name into
the Illuminate subject vocabulary. Six source models each define their own copy,
so a source model has to know about Illuminate, and a new subject means six
edits.

## What the diagnostic changed

Two findings from re-running the issue's diagnostic contradict its body. Both
change the design.

### Four consumers, not two

The issue names `int_assessments__score_anchors` and
`fct_assessment_scores_enrollment_scoped`. Two more read the column:

| Consumer                                     | Reads from     | Use                                                |
| -------------------------------------------- | -------------- | -------------------------------------------------- |
| `int_extracts__student_enrollments_subjects` | pearson, fldoe | joins it against its own `illuminate_subject_area` |
| `rpt_tableau__academic_goals_rollup`         | pearson, fldoe | maps it straight back to `Reading` / `Math`        |

`int_iready__domain_unpivot` also selects it through from
`int_iready__diagnostic_results`.

### The six copies are four expressions over four different input columns

They are not one vocabulary being duplicated:

| Source          | Input column                     | Expression                                                                    |
| --------------- | -------------------------------- | ----------------------------------------------------------------------------- |
| i-Ready         | `subject`                        | `Reading` to `Text Study`, `Math` to `Mathematics`, no `else`                 |
| Amplify         | none                             | literal `'Text Study'`                                                        |
| Ren Learn       | `_dagster_partition_subject`     | `SM` to `Mathematics`, `else 'Text Study'`                                    |
| Pearson / FLDOE | `subject` / `assessment_subject` | ELA to `Text Study`, Algebra and Geometry to `Mathematics`, else pass through |
| Cambium NJGPA   | `subject`                        | ELA to `Text Study`, else pass through. No math arm.                          |

So "define the mapping once in the blended layer" does not follow by itself.
Both blended consumers read all six sources in parallel per-source CTEs, so
relocating each `CASE` downstream writes it once per consumer rather than once
overall.

### The mapping is 18 rows over 4 target values

Every distinct `(source, raw subject)` pair present in prod, with row counts as
of 2026-09-16:

| Source          | Raw subject                           | Illuminate subject | Rows    |
| --------------- | ------------------------------------- | ------------------ | ------- |
| iready          | `Math`                                | Mathematics        | 154,933 |
| iready          | `Reading`                             | Text Study         | 119,204 |
| pearson+cambium | `Mathematics`                         | Mathematics        | 28,689  |
| pearson+cambium | `English Language Arts`               | Text Study         | 20,848  |
| pearson+cambium | `English Language Arts/Literacy`      | Text Study         | 11,626  |
| pearson+cambium | `Science`                             | Science            | 6,920   |
| pearson+cambium | `Algebra I`, `Geometry`, `Algebra II` | Mathematics        | 3,938   |
| fldoe           | `English Language Arts`               | Text Study         | 11,651  |
| fldoe           | `Mathematics`                         | Mathematics        | 10,847  |
| fldoe           | `Science`                             | Science            | 883     |
| fldoe           | `Civics`                              | Civics             | 398     |
| fldoe           | `Algebra I`                           | Mathematics        | 204     |
| renlearn        | `SM`                                  | Mathematics        | 4,075   |
| renlearn        | `SR`, `SEL`                           | Text Study         | 4,212   |
| amplify         | none (constant)                       | Text Study         | all     |

Ren Learn `SEL` (Star Early Literacy) resolves to `Text Study` only through the
`else` branch. 1,365 rows rest on a default rather than a stated rule.

## Why a sheet, and why a new tab

`stg_google_sheets__assessments__course_subject_crosswalk` already holds the
Illuminate vocabulary for the join-target side: PowerSchool course number to
`Illuminate_Subject_Area`, analyst-editable, 47 distinct subject areas. It is
the precedent for where this vocabulary lives.

It cannot absorb the vendor mapping. Its grain is one row per PowerSchool course
number, with an error-severity `unique` test on that column. The vendor mapping
is keyed on a vendor or state subject name, a different key space. Adding vendor
rows with a null course number works mechanically, but leaves `Is_Foundations`,
`Is_Advanced_Math` and `Discipline` meaningless on those rows and
`Source_System` meaningless on the 300-plus course rows. Adding vendor columns
to the existing rows does not work at all: 62 course rows map to `Text Study`,
and `Reading` belongs to the subject area, not to any one of those courses.

A sibling tab keeps one grain per tab.

## Design

### 1. The crosswalk

New tab `src_assessments__vendor_subject_crosswalk` on the existing assessments
spreadsheet (`1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE`), three columns:

- `Source_System` — `iready`, `pearson`, `fldoe`, `renlearn`, `amplify`
- `Raw_Subject`
- `Illuminate_Subject_Area`

Populated with the 18 rows above: the 17 pairs present in prod, plus the Amplify
row. Cambium folds under `pearson`: it already unions into the kipptaf Pearson
wrapper, and its `English Language Arts/Literacy` spelling gets its own row.
Amplify gets one row, `('amplify', 'DIBELS', 'Text Study')`.

Supporting dbt objects:

- Source entry in `src/dbt/kipptaf/models/google/sheets/sources-external.yml`,
  with a `dagster.asset_key` matching its siblings.
- `stg_google_sheets__assessments__vendor_subject_crosswalk`, a `select *,` over
  that source, matching the sheet's header case as the sibling crosswalk does.
- `dbt_utils.unique_combination_of_columns` on `(Source_System, Raw_Subject)`,
  error severity.

### 2. Source models drop the column

All six already project their raw subject, so no new column is exposed anywhere:

| Model                            | Project   | Raw column that stays        |
| -------------------------------- | --------- | ---------------------------- |
| `int_iready__diagnostic_results` | kipptaf   | `subject`                    |
| `int_amplify__all_assessments`   | kipptaf   | none; see below              |
| `stg_renlearn__star`             | kipptaf   | `_dagster_partition_subject` |
| `int_pearson__all_assessments`   | pearson   | `subject`                    |
| `int_fldoe__all_assessments`     | kippmiami | `assessment_subject`         |
| `stg_cambium__njgpa`             | cambium   | `subject`                    |

`stg_cambium__njgpa` is contract-enforced, so its properties file changes with
it. `int_iready__domain_unpivot` stops selecting the column through.

Amplify has no raw subject column at all — `illuminate_subject` is a bare
literal. Its blended-layer CTE supplies `'DIBELS' as raw_subject`. That literal
is a fact about the source (DIBELS measures literacy), not about Illuminate; the
translation to `Text Study` stays in the crosswalk.

The two kipptaf per-source wrappers drop it as well: from the `include=[...]`
list in `int_pearson__all_assessments`, and from the fldoe passthrough.

### 3. The blended layer resolves it, once per union

Each consumer already funnels its per-source branches into a single union CTE
that already carries a source discriminator. The crosswalk therefore joins once
per union, not once per source — five join sites, not fifteen:

| Consumer                                     | Union CTE            | Discriminator          |
| -------------------------------------------- | -------------------- | ---------------------- |
| `int_assessments__score_anchors`             | `scores`             | `source_type`, exists  |
| `fct_assessment_scores_enrollment_scoped`    | `state_union`        | `score_source`, exists |
| `fct_assessment_scores_enrollment_scoped`    | `vendor_all`         | `score_source`, exists |
| `int_extracts__student_enrollments_subjects` | `prev_yr_state_test` | add a literal          |
| `rpt_tableau__academic_goals_rollup`         | `state_test_union`   | add a literal          |

Each branch selects its raw column as `raw_subject`. One `left join` to the
crosswalk after the union produces `subject_area`.

The discriminator literals already in the SQL (`'state_nj'`, `'state_fl'`,
`'iready'`, `'star'`, `'dibels'`) do not match the crosswalk's `Source_System`
values. Add a separate `source_system` literal per branch rather than renaming
the existing discriminators, which are load-bearing elsewhere — the resolver
joins on `sr.source_type`.

### 4. Unmapped subjects coalesce, and a test catches them

Pearson, FLDOE and Cambium currently `else <subject>`: an unmapped subject
passes through unchanged. A bare left join would yield NULL instead, and NULL
never matches `illuminate_subject_area` at the resolver join in
`int_assessments__resolved_section_enrollments`, so those rows would silently
drop.

Each join site therefore reads
`coalesce(x.Illuminate_Subject_Area, u.raw_subject)`, preserving current
behavior exactly, plus a warn-severity singular test listing any
`(source_system, raw_subject)` pair the crosswalk misses.

One deliberate behavior change: Ren Learn's `else 'Text Study'` means a new Star
product code is today silently called Text Study. Under the crosswalk it passes
through as its raw code and trips the warn test instead. `SEL` keeps mapping to
`Text Study` because it gets an explicit row.

### 5. Shipping order

A column drop reverses the usual add order: the consumer stops reading before
the producer removes.

1. The sheet tab is created and populated. Manual, and it gates everything else.
2. PR 1, kipptaf: crosswalk source entry, staging model and test; the five join
   sites; drop the column from the four kipptaf-owned source models and both
   wrappers.
3. PR 2, districts and packages: drop it from `pearson`
   `int_pearson__all_assessments`, `kippmiami` `int_fldoe__all_assessments`, and
   `cambium` `stg_cambium__njgpa`.

PR 1 must land and materialize in prod before PR 2, or the kipptaf
`union_relations` wrapper's compile-time column list still expects the column.

## Verification

- `fct_assessment_scores_enrollment_scoped`: `count(*)` and
  `count(distinct format("%T|%T", ...))` on its key, PR branch versus prod.
  Unchanged. This is the issue's stated acceptance bar.
- Same comparison for `int_assessments__score_anchors`,
  `int_extracts__student_enrollments_subjects` and
  `rpt_tableau__academic_goals_rollup` — the two the issue did not name are
  included deliberately.
- The unmapped-pair test returns zero rows against current data.
- `rg 'illuminate_subject\b' -g '*.sql' src/dbt` returns no hits on any
  source-system staging or intermediate model.

## Out of scope

- `illuminate_subject_area` on the course-enrollment side
  (`int_students__course_enrollments`, `int_assessments__course_enrollments`) is
  the join target, not a copy of this mapping.
- `stg_google_sheets__dibels__expected_assessments_by_levels` carries a
  sheet-supplied `illuminate_subject` column of its own. It is a seventh place
  the vocabulary appears and is not one of the six.
- The course side carries `Geometry` (12 courses), `Algebra I` (16) and
  `Algebra II` (4) as distinct subject areas, but Pearson collapses all three to
  `Mathematics` before the resolver join, so only the four coarse values ever
  match. If that is unintended it deserves its own issue; this refactor
  preserves the current behavior either way.

## Risks

- The assessments spreadsheet shares one URI across tabs, so any edit to the new
  tab re-triggers every tab's Dagster asset.
- Step 1 is a manual sheet edit outside this repo. Nothing downstream can be
  built or tested until it exists.
