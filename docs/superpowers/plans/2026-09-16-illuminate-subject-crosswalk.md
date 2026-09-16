# Vendor-to-Illuminate Subject Crosswalk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace six per-source `illuminate_subject` definitions with one
analyst-editable Google Sheet crosswalk that the blended assessment layer joins.

**Architecture:** A new sheet tab maps `(Source_System, Raw_Subject)` to
`Illuminate_Subject_Area`. Each of the four blended consumers already funnels
its per-source branches into one union CTE carrying a source discriminator, so
the crosswalk joins once per union — five join sites, not one per source. The
six source models keep their raw subject column and drop the derived one.

**Tech Stack:** dbt on BigQuery, Google Sheets external tables, dbt Cloud CI,
Dagster.

Spec:
`docs/superpowers/specs/2026-09-16-illuminate-subject-crosswalk-design.md`. Refs
[#5340](https://github.com/TEAMSchools/teamster/issues/5340).

## Global Constraints

- **The resolved column keeps the name it already has in each consumer.** In
  `fct_assessment_scores_enrollment_scoped` it stays `illuminate_subject`; in
  `int_assessments__score_anchors` it stays `subject_area`. Renaming either
  moves a join predicate or a surrogate-key input. Specifically,
  `fct_assessment_scores_enrollment_scoped.sql:625` hashes `su.subject_area`
  into `assessment_score_key`, and `su.subject_area` is Pearson's own
  `subject_area` column, NOT the Illuminate value. Do not touch it.
- **The crosswalk is keyed on the column each source's `CASE` reads today** —
  Pearson and Cambium on `subject`, FLDOE on `assessment_subject`, i-Ready on
  `subject`, Ren Learn on `_dagster_partition_subject`. Not on `subject_area`,
  which differs from `subject` on the Pearson side.
- **Every join site is a `LEFT JOIN` with
  `coalesce(x.illuminate_subject_area, <raw column>)`.** A bare join yields NULL
  for an unmapped subject, and NULL never matches at the resolver, so rows would
  silently drop.
- **Reference the crosswalk's columns in lowercase in SQL** — `x.source_system`,
  `x.raw_subject`, `x.illuminate_subject_area`. The columns are declared
  PascalCase in the sheet and the properties file, but sqlfluff CP02 rewrites
  identifier references to lowercase and BigQuery resolves column references
  case-insensitively, so the lowercase form binds correctly. Verified against
  the built crosswalk. Only the YAML declarations stay PascalCase.
- **Every literal in a UNION ALL branch needs an explicit alias** — write
  `'pearson' as source_system`, never a bare `'pearson'`. sqlfluff AL03 fails
  the bare form.
- Two PRs. PR 1 is kipptaf only. PR 2 drops the column from the `pearson`,
  `kippmiami` and `cambium` projects, and lands only after PR 1 has materialized
  in prod.
- dbt is always `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf`. Never
  bare `dbt`. A fresh worktree needs `uv run dbt deps --project-dir ...` once
  before any build.
- Invoke the `dbt-local-dev` skill before the first local build, and the
  `trunk-lint` skill before the first push.

---

## Task 0: Create and populate the sheet tab

This task is the user's. It is manual, outside the repo, and gates every other
task. Nothing below can be built or tested until it is done.

**Files:** none in this repo.

**Interfaces:**

- Produces: a tab named `src_assessments__vendor_subject_crosswalk` on
  spreadsheet `1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE`, header row
  `Source_System | Raw_Subject | Illuminate_Subject_Area`, 18 data rows.

- [ ] **Step 1: Add the tab with exactly this content**

Header row 1, data from row 2. Values are case-sensitive and must match the
source data character for character.

| Source_System | Raw_Subject                    | Illuminate_Subject_Area |
| ------------- | ------------------------------ | ----------------------- |
| iready        | Reading                        | Text Study              |
| iready        | Math                           | Mathematics             |
| pearson       | English Language Arts          | Text Study              |
| pearson       | English Language Arts/Literacy | Text Study              |
| pearson       | Mathematics                    | Mathematics             |
| pearson       | Algebra I                      | Mathematics             |
| pearson       | Algebra II                     | Mathematics             |
| pearson       | Geometry                       | Mathematics             |
| pearson       | Science                        | Science                 |
| fldoe         | English Language Arts          | Text Study              |
| fldoe         | Mathematics                    | Mathematics             |
| fldoe         | Algebra I                      | Mathematics             |
| fldoe         | Science                        | Science                 |
| fldoe         | Civics                         | Civics                  |
| renlearn      | SM                             | Mathematics             |
| renlearn      | SR                             | Text Study              |
| renlearn      | SEL                            | Text Study              |
| amplify       | DIBELS                         | Text Study              |

- [ ] **Step 2: Confirm the tab name has no trailing space**

The `sheet_range` in the source YAML must match the tab name exactly. A trailing
space produces an external table that fails at build with a table-not-found
error.

---

## Task 1: Crosswalk source, staging model and uniqueness test

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (add an
  entry beside `src_google_sheets__assessments__course_subject_crosswalk`,
  around line 1281)
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__assessments__vendor_subject_crosswalk.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__assessments__vendor_subject_crosswalk.yml`

**Interfaces:**

- Consumes: the sheet tab from Task 0.
- Produces: model `stg_google_sheets__assessments__vendor_subject_crosswalk`
  with columns `Source_System`, `Raw_Subject`, `Illuminate_Subject_Area`, all
  STRING. Every later task refs this model and reads those three column names in
  that exact case.

- [ ] **Step 1: Add the source entry**

In `sources-external.yml`, directly after the
`src_google_sheets__assessments__course_subject_crosswalk` block:

```yaml
- name: src_google_sheets__assessments__vendor_subject_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE
      sheet_range: src_assessments__vendor_subject_crosswalk
      skip_leading_rows: 1
  columns:
    - name: Source_System
      data_type: string
    - name: Raw_Subject
      data_type: string
    - name: Illuminate_Subject_Area
      data_type: string
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - sheets
          - assessments
          - vendor_subject_crosswalk
```

- [ ] **Step 2: Write the staging model**

Create the `.sql` file with exactly this content. The trailing comma after `*`
satisfies sqlfluff CV03; the sibling `course_subject_crosswalk` model has the
same shape.

```sql
select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__assessments__vendor_subject_crosswalk",
        )
    }}
```

- [ ] **Step 3: Write the properties file**

Column names match the sheet header case because the model is `select *` and
`staging/` is contract-enforced at directory level.

```yaml
models:
  - name: stg_google_sheets__assessments__vendor_subject_crosswalk
    description:
      Maps each assessment vendor's or state's own subject name onto the
      Illuminate subject vocabulary. Keyed on the raw subject column that source
      reports, not on a normalized one. Cambium rows sit under source system
      pearson because Cambium unions into int_pearson__all_assessments before
      any consumer reads it.
    columns:
      - name: Source_System
        data_type: string
        description:
          One of iready, pearson, fldoe, renlearn, amplify. The value each
          blended union CTE supplies as a literal.
      - name: Raw_Subject
        data_type: string
        description:
          The subject value as the source reports it. Pearson and Cambium report
          subject, FLDOE assessment_subject, i-Ready subject, Ren Learn
          _dagster_partition_subject. Amplify reports none, so it carries the
          literal DIBELS.
      - name: Illuminate_Subject_Area
        data_type: string
        description:
          The Illuminate subject area, matching the vocabulary in
          stg_google_sheets__assessments__course_subject_crosswalk.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - Source_System
              - Raw_Subject
          config:
            severity: error
```

`combination_of_columns` nests under `arguments:`. The flat form raises
`MissingArgumentsPropertyInGenericTestDeprecation` at parse time, and 209 of the
213 `unique_combination_of_columns` declarations in this project already use the
nested form.

- [ ] **Step 4: Stage the external table and build**

```bash
uv run dbt deps --project-dir src/dbt/kipptaf
```

Then, in a separate call:

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__assessments__vendor_subject_crosswalk" \
  --project-dir src/dbt/kipptaf
uv run dbt build --select stg_google_sheets__assessments__vendor_subject_crosswalk \
  --project-dir src/dbt/kipptaf
```

Expected: PASS, 18 rows, uniqueness test green.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/
git commit -m "feat(dbt): add the vendor-to-Illuminate subject crosswalk

Refs #5340"
```

---

## Task 2: Exhaustiveness test

Written and run before any consumer changes, so it proves the crosswalk covers
every live pair while the source models still hold their own `CASE`.

**Files:**

- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources.sql`

**Interfaces:**

- Consumes: `stg_google_sheets__assessments__vendor_subject_crosswalk` from
  Task 1.
- Produces: nothing other tasks read. It stays in place after the refactor as
  the standing guard.

- [ ] **Step 1: Write the test**

The shape follows `tests/int_collegeboard__ap_unpivot__crosswalk_resolves.sql`:
select the offending rows, and dbt fails the test when any come back. Amplify is
absent from the union because it has no raw subject column to drift.

```sql
with
    raw_subjects as (
        select distinct 'iready' as source_system, `subject` as raw_subject,
        from {{ ref("int_iready__diagnostic_results") }}

        union all

        select distinct 'pearson' as source_system, `subject` as raw_subject,
        from {{ ref("int_pearson__all_assessments") }}

        union all

        select distinct 'fldoe' as source_system, assessment_subject as raw_subject,
        from {{ ref("int_fldoe__all_assessments") }}

        union all

        select distinct
            'renlearn' as source_system, _dagster_partition_subject as raw_subject,
        from {{ ref("stg_renlearn__star") }}
    )

select r.source_system, r.raw_subject,
from raw_subjects as r
left join
    {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
    on r.source_system = x.source_system
    and r.raw_subject = x.raw_subject
where r.raw_subject is not null and x.raw_subject is null
```

- [ ] **Step 2: Register the test with warn severity**

Append to `src/dbt/kipptaf/tests/properties.yml`:

```yaml
- name: stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources
  description:
    Lists any source-and-raw-subject pair present in the data but missing from
    the crosswalk. Warn, not error, because an unmapped subject falls back to
    its raw value rather than dropping the row.
  config:
    severity: warn
```

That file exists and already registers the sibling singular tests, including
`int_collegeboard__ap_unpivot__crosswalk_resolves`. Match the surrounding
indentation.

- [ ] **Step 3: Run the test and confirm it passes on current data**

```bash
uv run dbt build --select stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources \
  --project-dir src/dbt/kipptaf
```

Expected: PASS, 0 rows. A non-zero result means the sheet is missing a pair —
add it to the sheet rather than weakening the test.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/tests/
git commit -m "test(dbt): guard vendor subject crosswalk coverage

Refs #5340"
```

---

## Task 3: Resolve the crosswalk in `int_assessments__score_anchors`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`

**Interfaces:**

- Consumes: `stg_google_sheets__assessments__vendor_subject_crosswalk`.
- Produces: no change to this model's output columns. `subject_area` keeps its
  name, position and meaning. `int_assessments__resolved_section_enrollments`
  reads it and must be unaffected.

- [ ] **Step 1: Capture the prod baseline**

Run through the BigQuery MCP and record both numbers:

```sql
select
  count(*) as n_rows,
  count(distinct format("%T|%T|%T|%T",
    powerschool_student_number, source_type, subject_area, anchor_date)) as n_keys
from `teamster-332318.kipptaf_assessments.int_assessments__score_anchors`
```

- [ ] **Step 2: Swap each source CTE from the derived column to the raw one**

Five CTEs each replace `illuminate_subject as subject_area,` with a raw column
plus a source literal. Replace in `state_nj_scores`:

```sql
            `subject` as raw_subject,
            'pearson' as source_system,
```

In `state_fl_scores`:

```sql
            assessment_subject as raw_subject,
            'fldoe' as source_system,
```

In `iready_scores`:

```sql
            `subject` as raw_subject,
            'iready' as source_system,
```

In `star_scores`:

```sql
            _dagster_partition_subject as raw_subject,
            'renlearn' as source_system,
```

In `dibels_scores`:

```sql
            'DIBELS' as raw_subject,
            'amplify' as source_system,
```

`internal_scores` gets no crosswalk. Give it
`cast(null as string) as raw_subject,` and
`cast(null as string) as source_system,` so the UNION ALL branches line up
positionally.

- [ ] **Step 3: Carry both new columns through the `scores` union**

Every one of the six branches in the `scores` CTE lists its columns explicitly.
Add `raw_subject,` and `source_system,` to each branch in the same position, and
REMOVE `subject_area,` from each branch — it is now derived below, not carried.

- [ ] **Step 4: Resolve once in the final SELECT**

The model currently ends by selecting from `scores`. Change that tail so the
crosswalk joins once and reproduces `subject_area`:

```sql
select
    s.powerschool_student_number,
    s.canonical_assessment_id,
    s.academic_year,
    s.administration_period,
    s._dbt_source_project,
    s.anchor_date,
    s.source_type,

    coalesce(x.illuminate_subject_area, s.raw_subject) as subject_area,
from scores as s
left join
    {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
    on s.source_system = x.source_system
    and s.raw_subject = x.raw_subject
```

Keep any column the existing tail already projects. `coalesce` is a simple
function, so sqlfluff ST06 wants it after the plain column refs — that is why it
sits last.

`internal_scores` rows carry NULL on both key columns, so the join misses and
`coalesce` returns NULL — which is what `subject_area` already is for internal
rows today.

- [ ] **Step 5: Build the model and its tests**

```bash
uv run dbt build --select int_assessments__score_anchors \
  --project-dir src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 6: Compare against the baseline**

Re-run the Step 1 query against the dev relation the build produced. Both
numbers must match the prod baseline exactly. If `n_keys` drops, a `coalesce` is
missing somewhere and rows collapsed onto NULL.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql
git commit -m "refactor(dbt): resolve subject_area from the crosswalk in score anchors

Refs #5340"
```

---

## Task 4: Resolve the crosswalk in `fct_assessment_scores_enrollment_scoped`

Two join sites in one file: `state_union` and `vendor_all`.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

**Interfaces:**

- Consumes: `stg_google_sheets__assessments__vendor_subject_crosswalk`.
- Produces: no output column change. `illuminate_subject` keeps its name on both
  `state_union` and `vendor_all`, so the join predicates at lines 694 and 785
  are untouched.

- [ ] **Step 1: Capture the prod baseline**

```sql
select
  count(*) as n_rows,
  count(distinct assessment_score_key) as n_keys
from `teamster-332318.kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

- [ ] **Step 2: Add raw columns to the two state branches**

In `state_nj` (around line 55), replace `illuminate_subject,` with:

```sql
            `subject` as raw_subject,
```

and add, beside the existing `'state_nj' as score_source,`:

```sql
            'pearson' as source_system,
```

Leave `subject_area,` exactly as it is — it feeds the `assessment_score_key`
hash at line 625.

In `state_fl` (around line 86), replace `illuminate_subject,` with:

```sql
            assessment_subject as raw_subject,
```

and add beside `'state_fl' as score_source,`:

```sql
            'fldoe' as source_system,
```

- [ ] **Step 3: Carry the new columns through `state_all`**

`state_all` enumerates its columns in both UNION ALL branches. In each branch,
replace `illuminate_subject,` with `raw_subject,` and add `source_system,`.

- [ ] **Step 4: Resolve at `state_union`**

`state_union` currently reads
`select sa.*, coalesce(...) as student_identifier, from state_all as sa`. Add
the crosswalk join and re-derive the column under its original name:

```sql
    state_union as (
        select
            sa.*,

            coalesce(
                cast(sa.student_number as string), sa.state_student_id
            ) as student_identifier,

            coalesce(x.illuminate_subject_area, sa.raw_subject) as illuminate_subject,
        from state_all as sa
        left join
            {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
            on sa.source_system = x.source_system
            and sa.raw_subject = x.raw_subject
    ),
```

- [ ] **Step 5: Add raw columns to the four vendor branches**

In each vendor CTE, replace `illuminate_subject,` with a raw column and add a
source literal beside the existing `score_source`:

`iready_scores_raw` (around line 175) — note `subject` is already consumed as
`module_code`, so project it a second time:

```sql
            `subject` as raw_subject,
            'iready' as source_system,
```

The i-Ready domain-unpivot branch (reads `int_iready__domain_unpivot`, around
line 237):

```sql
            `subject` as raw_subject,
            'iready' as source_system,
```

The STAR branch (reads `stg_renlearn__star`, around line 381):

```sql
            _dagster_partition_subject as raw_subject,
            'renlearn' as source_system,
```

The DIBELS branch (reads `int_amplify__all_assessments`, around line 450):

```sql
            'DIBELS' as raw_subject,
            'amplify' as source_system,
```

- [ ] **Step 6: Carry the new columns through `vendor_all` and resolve there**

`vendor_all` enumerates its columns in every UNION ALL branch. In each branch,
replace `illuminate_subject,` with `raw_subject,` and add `source_system,`.

Because `vendor_all` is itself the union, the crosswalk cannot join inside it.
Add a new CTE immediately after it:

```sql
    vendor_resolved as (
        select
            va.*,

            coalesce(x.illuminate_subject_area, va.raw_subject) as illuminate_subject,
        from vendor_all as va
        left join
            {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
            on va.source_system = x.source_system
            and va.raw_subject = x.raw_subject
    ),
```

Then change `from vendor_all as va` at line 776 to `from vendor_resolved as va`.
The join predicate at line 785, `and va.illuminate_subject = sr.subject_area`,
needs no edit.

- [ ] **Step 7: Update the two explanatory comments**

The comments above lines 694 and 785 describe `illuminate_subject` as coming
from the source model. Both now read from the crosswalk. Rewrite the first as:

```sql
-- the resolver keys state scores on illuminate_subject (the crosswalk's
-- state->Illuminate subject mapping), not the raw subject_area the
-- assessment_score_key hashes. join on su.illuminate_subject = sr.subject_area
-- or every row drops. INNER scopes the fact to state scores with a resolved
-- section.
```

and the second as:

```sql
-- the resolver keys vendor scores on illuminate_subject (the crosswalk's
-- vendor->Illuminate subject mapping), not the raw vendor subject the
-- assessment_score_key hashes. INNER scopes the fact to vendor scores with a
-- resolved section.
```

- [ ] **Step 8: Build and compare**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf
```

Expected: PASS. Then re-run the Step 1 query against the dev relation. Both
counts must match prod exactly. This is the issue's stated acceptance bar.

- [ ] **Step 9: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql
git commit -m "refactor(dbt): resolve illuminate_subject from the crosswalk in the scores fact

Refs #5340"
```

---

## Task 5: Resolve the crosswalk in `int_extracts__student_enrollments_subjects`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql`
  (the `prev_yr_state_test` CTE, lines 52-90)

**Interfaces:**

- Consumes: `stg_google_sheets__assessments__vendor_subject_crosswalk`.
- Produces: no output column change. `py.subject` keeps its name and is joined
  at line 311 against `sj.illuminate_subject_area`.

- [ ] **Step 1: Capture the prod baseline**

```sql
select count(*) as n_rows
from `teamster-332318.kipptaf_students.int_extracts__student_enrollments_subjects`
```

- [ ] **Step 2: Replace the derived column in both union branches**

In the Pearson branch (line 59), replace `illuminate_subject as \`subject\`,`
with:

```sql
            `subject` as raw_subject,
            'pearson' as source_system,
```

In the FLDOE branch (line 78), replace `illuminate_subject as \`subject\`,`
with:

```sql
            assessment_subject as raw_subject,
            'fldoe' as source_system,
```

- [ ] **Step 3: Wrap the union in a resolving CTE**

`prev_yr_state_test` is itself the UNION ALL, so add a new CTE right after it
that produces the `subject` column the downstream join expects:

```sql
    prev_yr_state_test_resolved as (
        select
            p.*,

            coalesce(x.illuminate_subject_area, p.raw_subject) as `subject`,
        from prev_yr_state_test as p
        left join
            {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
            on p.source_system = x.source_system
            and p.raw_subject = x.raw_subject
    ),
```

Then change `from prev_yr_state_test as py` at line 306 to
`from prev_yr_state_test_resolved as py`.

`raw_subject` and `source_system` ride along in the `p.*` expansion. That is
harmless — the final SELECT reads `py` by named column only, never `py.*` — and
it keeps the CTE clear of `select * except`, which the SQL conventions reserve
for cases a standard form cannot express. It mirrors the `state_union` shape in
`fct_assessment_scores_enrollment_scoped`.

- [ ] **Step 4: Build and compare**

```bash
uv run dbt build --select int_extracts__student_enrollments_subjects \
  --project-dir src/dbt/kipptaf
```

Expected: PASS, row count matching the Step 1 baseline. This model cross joins
to a two-row `subjects` CTE, so a fan-out change would show as an exact doubling
— check the number, not just the build status.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql
git commit -m "refactor(dbt): resolve prior-year state subject from the crosswalk

Refs #5340"
```

---

## Task 6: Resolve the crosswalk in `rpt_tableau__academic_goals_rollup`

This consumer maps the Illuminate value straight back to `Reading` / `Math`, so
the crosswalk join replaces the inbound half of a round trip.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__academic_goals_rollup.sql`
  (the `state_test_union` CTE, lines 33-115)

**Interfaces:**

- Consumes: `stg_google_sheets__assessments__vendor_subject_crosswalk`.
- Produces: no output column change. The `subject` column keeps its `Reading` /
  `Math` values.

- [ ] **Step 1: Capture the prod baseline**

```sql
select count(*) as n_rows,
  count(distinct format("%T|%T", student_number, `subject`)) as n_keys
from `teamster-332318.kipptaf_tableau.rpt_tableau__academic_goals_rollup`
```

- [ ] **Step 2: Replace the three derived expressions with raw columns**

In the NJSLA branch (lines 49-53), replace the whole
`case when illuminate_subject = 'Text Study' ... end as \`subject\`,` with:

```sql
            `subject` as raw_subject,
            'pearson' as source_system,
```

In both FAST branches (lines 77 and 103), replace
`if(f.illuminate_subject = 'Text Study', 'Reading', 'Math') as \`subject\`,`
with:

```sql
            f.assessment_subject as raw_subject,
            'fldoe' as source_system,
```

Note the NJSLA branch's `WHERE` clause already filters on `` `subject` ``
(`and not (assessmentgrade = 'Grade 8' and \`subject\` like 'Algebra%')`). That
predicate reads the source model's own column and is unaffected.

- [ ] **Step 3: Wrap the union in a resolving CTE**

Add a CTE right after `state_test_union`:

```sql
    state_test_resolved as (
        select
            s.*,

            case
                when coalesce(x.illuminate_subject_area, s.raw_subject) = 'Text Study'
                then 'Reading'
                else 'Math'
            end as `subject`,
        from state_test_union as s
        left join
            {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
            on s.source_system = x.source_system
            and s.raw_subject = x.raw_subject
    ),
```

The NJSLA branch previously returned NULL for anything that was neither
`Text Study` nor `Mathematics`, while the FAST branches returned `Math`. This
`else 'Math'` matches the FAST behavior for both. Confirm in Step 4 that the row
and key counts are unchanged; if `n_keys` shifts, restore the NJSLA branch's
three-way `CASE` as a separate expression rather than sharing one.

Then change every reference to `state_test_union` further down the model to
`state_test_resolved`. Find them with
`rg -n 'state_test_union' src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__academic_goals_rollup.sql`.

- [ ] **Step 4: Build and compare**

```bash
uv run dbt build --select rpt_tableau__academic_goals_rollup \
  --project-dir src/dbt/kipptaf
```

Expected: PASS, both counts matching the Step 1 baseline.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__academic_goals_rollup.sql
git commit -m "refactor(dbt): resolve state subject from the crosswalk in the goals rollup

Refs #5340"
```

---

## Task 7: Drop the column from the kipptaf-owned models

Every consumer now reads the crosswalk, so the producers can stop deriving it.
This task covers only models kipptaf owns. The three district and package models
wait for PR 2.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__diagnostic_results.sql`
  (the `CASE` at lines 153-155)
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__diagnostic_results.yml`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql`
  (lines 7 and 98)
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`
- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/int_amplify__all_assessments.sql`
  (lines 229 and 287)
- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/properties/int_amplify__all_assessments.yml`
- Modify: `src/dbt/kipptaf/models/renlearn/staging/stg_renlearn__star.sql`
  (lines 43-45)
- Modify:
  `src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml`
- Modify:
  `src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
  (the `CASE` at lines 82-88)
- Modify:
  `src/dbt/kipptaf/models/fldoe/intermediate/properties/int_fldoe__all_assessments.yml`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
  (the `include=[...]` entry at line 38)
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml`

**Interfaces:**

- Consumes: nothing new.
- Produces: none of these models expose `illuminate_subject` any more. Every raw
  subject column Tasks 3 to 6 read stays in place.

- [ ] **Step 1: Confirm nothing still reads the column**

```bash
rg -n 'illuminate_subject\b' -g '*.sql' src/dbt/kipptaf/models
```

Expected: the only remaining hits are the six definitions listed above, plus
`fct_assessment_scores_enrollment_scoped` (where it is now the crosswalk's
output, not a source column) and the `stg_google_sheets__dibels__*` models,
which carry an unrelated sheet-supplied column and are out of scope.

- [ ] **Step 2: Delete the derivation in each SQL file**

For each `.sql` above, delete the `illuminate_subject` expression and its
trailing comma. `int_pearson__all_assessments.sql` is the exception: delete only
the `"illuminate_subject",` string from the `include` list, since that model
passes the column through rather than deriving it.

`int_iready__domain_unpivot.sql` has two references, lines 7 and 98. Delete
both.

`int_amplify__all_assessments.sql` has two `'Text Study' as illuminate_subject,`
literals, lines 229 and 287. Delete both.

- [ ] **Step 3: Delete the matching column entry from each properties file**

Each `.yml` above has an `- name: illuminate_subject` block. Delete the block
and any `data_tests` nested under it.

- [ ] **Step 4: Build the whole affected subtree**

```bash
uv run dbt build \
  --select int_iready__diagnostic_results+ int_amplify__all_assessments+ stg_renlearn__star+ int_fldoe__all_assessments+ int_pearson__all_assessments+ \
  --project-dir src/dbt/kipptaf
```

Expected: PASS. A `Name illuminate_subject not found` failure means a consumer
was missed — go back to Step 1 and widen the search to `.yml` as well.

- [ ] **Step 5: Confirm the acceptance criterion**

```bash
rg -n 'illuminate_subject\b' -g '*.sql' src/dbt/kipptaf/models/iready src/dbt/kipptaf/models/amplify src/dbt/kipptaf/models/renlearn src/dbt/kipptaf/models/fldoe src/dbt/kipptaf/models/pearson
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor(dbt): drop illuminate_subject from the kipptaf source models

Refs #5340"
```

---

## Task 8: Lint, push and open PR 1

**Files:** none new.

**Interfaces:**

- Produces: an open PR against `main`, referencing #5340.

- [ ] **Step 1: Lint every changed file**

Run from inside the worktree, and wait for the process to exit before reading
the output:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD) </dev/null
```

Expected: `No issues`. Fix anything it names before pushing.

- [ ] **Step 2: Push**

```bash
git push -u origin cbini/refactor/claude-illuminate-subject-crosswalk
```

- [ ] **Step 3: Open the PR**

Use the body structure from `.github/pull_request_template.md`. Include the four
baseline comparisons from Tasks 3 to 6 as a table of prod against PR-branch
counts. Reference the issue with `Refs #5340`, not `Closes #5340` — PR 2 closes
it.

- [ ] **Step 4: Watch dbt Cloud CI**

Invoke the `pr-ci-review` skill. `state:modified+` will pull a wide subtree, so
expect unrelated pre-existing warn tests as noise. Query prod for the same count
before attributing any failure to this change.

---

## Task 9: PR 2, drop the column from the district and package models

Starts only after PR 1 is merged AND Dagster has materialized the kipptaf models
in prod. Until then the kipptaf `union_relations` wrapper still resolves its
compile-time column list against district relations that carry the column.

**Files:**

- Modify: `src/dbt/pearson/models/intermediate/int_pearson__all_assessments.sql`
  (the `CASE` at lines 92-98)
- Modify:
  `src/dbt/pearson/models/intermediate/properties/int_pearson__all_assessments.yml`
- Modify:
  `src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
  (the `CASE` at lines 78-84)
- Modify:
  `src/dbt/kippmiami/models/fldoe/intermediate/properties/int_fldoe__all_assessments.yml`
- Modify: `src/dbt/cambium/models/staging/stg_cambium__njgpa.sql` (lines
  158-160)
- Modify: `src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: the column exists nowhere in `src/dbt`.

- [ ] **Step 1: Branch from a freshly fetched `main`**

```bash
gh issue develop 5340 --name cbini/refactor/claude-illuminate-subject-drop
git worktree add /workspaces/teamster/.worktrees/cbini/refactor/claude-illuminate-subject-drop \
  cbini/refactor/claude-illuminate-subject-drop
```

- [ ] **Step 2: Delete the derivation in each SQL file**

In `int_pearson__all_assessments.sql`, delete the six-line `CASE` ending
`end as illuminate_subject,`. In `int_fldoe__all_assessments.sql`, delete the
seven-line `CASE` ending `end as illuminate_subject,`. In
`stg_cambium__njgpa.sql`, delete the three-line `if(\`subject\` like 'English
Language Arts%', 'Text Study', \`subject\`) as illuminate_subject,`.

- [ ] **Step 3: Delete the matching column entry from each properties file**

`stg_cambium__njgpa` is contract-enforced, so the properties file is
authoritative — the build fails loudly if the column entry and the SQL disagree.
That is the intended guard, not a problem to work around.

- [ ] **Step 4: Build each project locally**

dbt Cloud CI covers kipptaf only, so these three need a local build:

```bash
uv run dbt build --select int_pearson__all_assessments --project-dir src/dbt/pearson
```

Then, separately:

```bash
uv run dbt build --select int_fldoe__all_assessments --project-dir src/dbt/kippmiami
uv run dbt build --select stg_cambium__njgpa --project-dir src/dbt/cambium
```

Expected: PASS on all three.

- [ ] **Step 5: Confirm the acceptance criterion repo-wide**

```bash
rg -n 'illuminate_subject\b' -g '*.sql' -g '*.yml' src/dbt
```

Expected: hits only in
`stg_google_sheets__assessments__vendor_subject_crosswalk` files, the five
blended consumers, and the out-of-scope `stg_google_sheets__dibels__*` models.
No source-system staging or intermediate model appears.

- [ ] **Step 6: Lint, commit, push and open PR 2**

```bash
git add -u
git commit -m "refactor(dbt): drop illuminate_subject from the district source models

Closes #5340"
```

Lint with the Task 8 Step 1 command, push, and open the PR with `Closes #5340`
in the body.

---

## Verification summary

The full acceptance bar from the issue and the spec, in one place:

| Check                                                        | Where          |
| ------------------------------------------------------------ | -------------- |
| `fct_assessment_scores_enrollment_scoped` counts unchanged   | Task 4, Step 8 |
| `int_assessments__score_anchors` counts unchanged            | Task 3, Step 6 |
| `int_extracts__student_enrollments_subjects` count unchanged | Task 5, Step 4 |
| `rpt_tableau__academic_goals_rollup` counts unchanged        | Task 6, Step 4 |
| Crosswalk covers every live pair                             | Task 2, Step 3 |
| No `illuminate_subject` on any source model                  | Task 9, Step 5 |
