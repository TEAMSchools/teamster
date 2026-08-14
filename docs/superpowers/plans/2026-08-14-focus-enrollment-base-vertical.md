# Focus Branch into the kipptaf Enrollment `base_` Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore KIPP Miami to `base_powerschool__student_enrollments` and its
15 consumer sites for AY2026, by building a Focus branch into a new SIS-neutral
`int_students__student_enrollments` that `base_` becomes a passthrough over.

**Architecture:** Three `focus` package models gain the homelessness and meal
custom-field conform. Three kipptaf models follow: a new `int_focus__advisory`,
a new `int_students__student_enrollments` that unions the three NJ district
`base_` models with a Focus-conformed block via `full union all corresponding`,
and `base_powerschool__student_enrollments` reduced to `select * from` the new
model. Single PR using the cross-project workflow.

**Tech Stack:** dbt 1.11 on BigQuery, `dbt_utils`, sqlfluff/markdownlint via
trunk, `uv` for all Python and dbt invocation.

**Spec:**
`docs/superpowers/specs/2026-08-14-focus-enrollment-base-vertical-design.md`

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base`.
  Every `git` call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/<project>`. Never
  `uv --directory <worktree> run dbt`.
- **Branch:** `cbini/feat/claude-focus-enrollment-base`, linked to issue #4868.
- **Python/dbt invocation:** always `uv run`. Never bare `dbt` or `python`.
- **Focus package models are built through a consuming district**, never
  standalone:
  `uv run dbt build --select <model> --project-dir <worktree>/src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev`.
- **Fresh worktree needs `dbt deps`** before the first build in each project
  dir.
- **`--state` must be absolute from a worktree:**
  `/workspaces/teamster/src/dbt/<project>/target/prod`.
- **Column vocabulary stays PowerSchool.** No R1-R10 renames in this PR.
- **SQL conventions** (`src/dbt/CLAUDE.md`): max 1 level of function nesting; no
  subqueries against tables or CTEs; no `ORDER BY`; no `QUALIFY`; no
  `GROUP BY ALL`; no lateral column aliases; no one-sided calculations in join
  predicates; no row-level calculations in `WHERE`; trailing commas in `SELECT`;
  single-quoted strings; 88-char lines. ST06 column order: plain refs grouped by
  source table, then constants, then `cast()`, then simple functions, then
  nested functions, then logicals, then `CASE`, then window functions.
- **Every new model needs** a `description:` on the model and every column, plus
  a uniqueness test. Staging models additionally need `config: severity: error`
  on every test.
- **Generic tests require `arguments:` nesting** (dbt 1.11+).
- **Do not run `trunk fmt` / `trunk check` manually** except on `.md` files
  before pushing — the pre-commit hook formats and the pre-push hook checks.
- **Never `git add -A` or `git add .`** — name files explicitly.
- **PII stays local.** No student values in commits, PR bodies, or issues.

---

## File Structure

**`focus` package** — the custom-field conform lives here, not at kipptaf:

- `src/dbt/focus/models/staging/stg_focus__students.sql` — add one column
- `src/dbt/focus/models/staging/properties/stg_focus__students.yml` — contract
  entry for it
- `src/dbt/focus/models/intermediate/int_focus__students__pivot.sql` — decode
  the new column
- `src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml`
- `src/dbt/focus/models/intermediate/int_focus__students.sql` — conform four
  network columns
- `src/dbt/focus/models/intermediate/properties/int_focus__students.yml`
- `src/dbt/focus/tests/unit/` — unit test for the conform CASE logic

**kipptaf**:

- `src/dbt/kipptaf/models/focus/intermediate/int_focus__advisory.sql` — new
- `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__advisory.yml`
  — new
- `src/dbt/kipptaf/models/focus/intermediate/int_focus__students.sql` — doc
  comment only, to force `state:modified`
- `src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql`
  — new, carries the body `base_` has today
- `src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml`
  — new, receives `base_`'s column docs and tests
- `src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql`
  — reduced to a passthrough
- `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__student_enrollments.yml`
  — reduced to a model-level description

---

## Task 1: Stage `custom_818` on `stg_focus__students`

**Files:**

- Modify: `src/dbt/focus/models/staging/stg_focus__students.sql:40`
- Modify: `src/dbt/focus/models/staging/properties/stg_focus__students.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: `stg_focus__students.homeless_unaccompanied_youth` (`NUMERIC`, the
  raw Focus option id — same type as its `custom_820` sibling).

Focus field `custom_818` is titled "Homeless Unaccompanied Youth". It is the
only field distinguishing `homeless_code` Y2 (unaccompanied) from Y1 (with
guardian). It lands in the dlt table but is not staged today.

- [ ] **Step 1: Confirm the raw column exists and its type**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
c = bigquery.Client(project='teamster-332318')
q = '''select column_name, data_type
from \`teamster-332318.dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS\`
where table_name = 'students' and column_name in ('custom_818','custom_820')'''
for r in c.query(q): print(dict(r))
"
```

Expected: both rows returned, matching data types. Record the type — the
properties YAML `data_type` must match it exactly.

- [ ] **Step 2: Add the column to the staging model**

In `src/dbt/focus/models/staging/stg_focus__students.sql`, immediately after the
`custom_820` line (line 40), add:

```sql
    custom_818 as homeless_unaccompanied_youth,
```

The surrounding lines for context — do not reorder them:

```sql
    custom_820 as homeless_student_pk_12,
    custom_818 as homeless_unaccompanied_youth,
    custom_863 as idea_educational_environment,
```

- [ ] **Step 3: Add the contract entry**

In `src/dbt/focus/models/staging/properties/stg_focus__students.yml`, find the
`homeless_student_pk_12` column entry and add a sibling immediately after it,
using the `data_type` recorded in Step 1:

```yaml
- name: homeless_unaccompanied_youth
  data_type: int64
  description:
    Focus select-field option id for Homeless Unaccompanied Youth. A five-option
    field — Y for not in a parent's or guardian's custody, C and U for the
    certified over-16 and under-16 variants of the same, N for homeless but
    accompanied, Z for not homeless. Decoded to a label in
    int_focus__students__pivot.
```

Do not describe this field as a flag or as "set only when" anything. Four of its
five codes describe states other than not-in-custody, and the interpretation
that turns it into a network homeless code belongs to Task 3, not here.

Match the `data_type` to Step 1's result. If Step 1 returned `NUMERIC`, use
`numeric`; `numeric` and `float64` are distinct BigQuery types and a mismatch
passes parse but fails the contract at build.

- [ ] **Step 4: Build the model to verify the contract**

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami
uv run dbt build --select stg_focus__students \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. A contract mismatch reports
`This model has an enforced contract that failed`. A `dbt build` is required
here — `dbt parse` and a prod `SELECT` both miss contract violations.

- [ ] **Step 5: Confirm the column carries data**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kippmiami_focus'
q = f'''select count(*) as n_rows,
countif(homeless_unaccompanied_youth is not null) as n_populated
from \`teamster-332318.{ds}.stg_focus__students\`'''
for r in c.query(q): print(dict(r))
"
```

Expected: `n_rows` around 3,989 and `n_populated` = 1. One populated row is the
correct current state, not a bug — see the spec's Ops follow-up.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/focus/models/staging/stg_focus__students.sql \
  src/dbt/focus/models/staging/properties/stg_focus__students.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "feat(focus): stage the homeless unaccompanied youth field

custom_818 is the only Focus field separating an unaccompanied homeless
student from one in a guardian's custody, which the network homeless_code
domain distinguishes as Y2 versus Y1.

Refs #4868"
```

---

## Task 2: Decode `custom_818` in `int_focus__students__pivot`

**Files:**

- Modify: `src/dbt/focus/models/intermediate/int_focus__students__pivot.sql`
- Modify:
  `src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__students.homeless_unaccompanied_youth` from Task 1.
- Produces: `int_focus__students__pivot.homeless_unaccompanied_youth_label`
  (`STRING`).

The model casts each custom field to `STRING` in an `encoded` CTE keyed by the
raw `custom_NNN` name, unpivots those into rows, joins the option labels, then
pivots the labels back out under readable aliases.

**There are THREE lists to edit, not two.** The `encoded` CTE, the `unpivoted`
CTE's `UNPIVOT (... for column_name in (...))` list, and the final
`pivot (... for column_name in (...))` list. Omitting the field from the
`encoded` or `unpivoted` list produces an always-null label column with no build
error — a silent failure. Grep the file for `custom_820` and add a sibling entry
at every one of the three sites it appears.

- [ ] **Step 1: Add the field to the `encoded` CTE**

In `int_focus__students__pivot.sql`, in the `encoded` CTE, immediately after the
`custom_820` line (around line 19), add:

```sql
            cast(homeless_unaccompanied_youth as string) as custom_818,
```

Context — do not reorder:

```sql
            cast(homeless_student_pk_12 as string) as custom_820,
            cast(homeless_unaccompanied_youth as string) as custom_818,
            cast(idea_educational_environment as string) as custom_863,
```

- [ ] **Step 2: Add the pivot output alias**

In the `pivot(... for column_name in (...))` list (around line 143), immediately
after the `custom_820` entry, add:

```sql
            'custom_818' as homeless_unaccompanied_youth_label,
```

Context:

```sql
            'custom_820' as homeless_student_pk_12_label,
            'custom_818' as homeless_unaccompanied_youth_label,
            'custom_863' as idea_educational_environment_label,
```

- [ ] **Step 3: Document the new column**

In `properties/int_focus__students__pivot.yml`, after the
`homeless_student_pk_12_label` entry, add:

```yaml
- name: homeless_unaccompanied_youth_label
  description: Decoded label for the homeless_unaccompanied_youth select field.
```

Keep it neutral, matching the plain one-line style every sibling `*_label`
column uses. Do not assert what the field means or how it maps to a network code
— it has five options describing different states, and the mapping is Task 3's
job.

- [ ] **Step 4: Build and verify the decode**

Run:

```bash
uv run dbt build --select int_focus__students__pivot \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS.

Then confirm the label resolves:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kippmiami_focus'
q = f'''select homeless_unaccompanied_youth_label as label, count(*) as n
from \`teamster-332318.{ds}.int_focus__students__pivot\`
group by 1'''
for r in c.query(q): print(dict(r))
"
```

Expected: one non-null label with `n` = 1, plus a null row for everyone else.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/focus/models/intermediate/int_focus__students__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "feat(focus): decode the homeless unaccompanied youth field

Refs #4868"
```

---

## Task 3: Conform homelessness and meal eligibility in `int_focus__students`

**Files:**

- Modify: `src/dbt/focus/models/intermediate/int_focus__students.sql`
- Modify: `src/dbt/focus/models/intermediate/properties/int_focus__students.yml`
- Create: `src/dbt/focus/models/intermediate/unit_tests.yml` (or append if it
  exists)

**Interfaces:**

- Consumes: `int_focus__students__pivot.homeless_unaccompanied_youth_label` from
  Task 2; the pre-existing `free_reduced_meals_program_label` and
  `homeless_student_pk_12_label`.
- Produces on `int_focus__students`: `homeless_code` (`STRING`), `is_homeless`
  (`BOOL`), `homeless_primary_nighttime_residence_code` (`INT64`), `lunchstatus`
  (`STRING`).

This model already conforms `spedlep`, `gifted_and_talented`, `lep_status`, and
`ethnicity` from `*_label` columns. The four new columns follow that pattern
exactly.

- [ ] **Step 1: Write the failing unit test**

Create or append to `src/dbt/focus/models/intermediate/unit_tests.yml`. Use
`format: sql` inputs, not dict rows — Task 1 added a column to
`stg_focus__students` in this same PR, and dict fixtures introspect the deferred
old-schema relation and reject the new column.

```yaml
unit_tests:
  - name: test_int_focus__students_homeless_and_meal_conform
    model: int_focus__students
    given:
      - input: ref('stg_focus__students')
        format: sql
        rows: |
          select 1 as student_id, 793 as homeless_student_pk_12,
            427 as homeless_unaccompanied_youth,
            15 as free_reduced_meals_program
          union all
          select 2, 789, 425, 24
          union all
          select 3, 790, 426, 21
          union all
          select 4, 794, cast(null as int64), 19
          union all
          select 5, 791, 7261, 22
      - input: ref('int_focus__students__pivot')
        format: sql
        rows: |
          select 1 as student_id,
            'Student is not homeless-default [N]' as homeless_student_pk_12_label,
            'Z- Not homeless (or student eligible for homeless services) but does not meet the definition of an unaccompanied youth. ' as homeless_unaccompanied_youth_label,
            'CEP NOT Direct Cert [N]' as free_reduced_meals_program_label
          union all
          select 2, 'Living in emergency or transitional shel [A]',
            'Y- Yes,who is not in the physical custody of parent or guardian [Y]',
            'The student is eligible for free meals [F]'
          union all
          select 3, 'Sharing the housing of other persons [B]',
            'N- No, Is homeless but does not meet the definiton of unaccompanied youth [N]',
            'Eligible for Reduced Lunch [3]'
          union all
          select 4, 'Student awaiting foster care [F]', cast(null as string),
            'Did Not Apply [0]'
          union all
          select 5, 'Living in cars, parks, temportary trailer parks or campgrounds, train stations, etc. [D]',
            'U - Student is a homeless child or youth (or student eligible for homeless services) under the age of 16 years who is not in the physical custody of a parent or guardian',
            'Eligible for Free Lunch with Direct Cert or extension of eligibility [D]'
    expect:
      format: sql
      rows: |
        select 1 as student_id, 'N' as homeless_code, false as is_homeless,
          cast(null as int64) as homeless_primary_nighttime_residence_code,
          cast(null as string) as lunchstatus
        union all
        select 2, 'Y2', true, 1, 'F'
        union all
        select 3, 'Y1', true, 2, 'R'
        union all
        select 4, 'Y1', true, cast(null as int64), 'P'
        union all
        select 5, 'Y2', true, 3, 'F'
```

The five cases cover: not homeless plus CEP; unaccompanied (`Y`) in a shelter
plus free meals; homeless but explicitly NOT unaccompanied (`N`), doubled-up,
reduced; awaiting foster care with no unaccompanied record at all,
did-not-apply; and unaccompanied-under-16 (`U`), unsheltered, free with direct
cert.

Cases 3 and 5 are the ones that matter. `custom_818` is a five-option field, not
a set/unset flag — a homeless student coded `N` is Y1, not Y2, so a null check
would mislabel them. Codes `Y`, `C`, and `U` all mean unaccompanied.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run dbt test --select test_int_focus__students_homeless_and_meal_conform \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: FAIL with a column-not-found error naming `homeless_code` — the model
does not produce these columns yet.

- [ ] **Step 3: Project the labels into the `labeled` CTE**

In `int_focus__students.sql`, in the `labeled` CTE's select list, after
`p.gifted_eligibility_label,` add:

```sql
            p.homeless_student_pk_12_label,
            p.homeless_unaccompanied_youth_label,
            p.free_reduced_meals_program_label,
```

- [ ] **Step 4: Add the four conformed columns**

In the final `select` of `int_focus__students.sql`, after the `lep_status` CASE
block and before the `ethnicity` block, add:

First derive both codes as named columns. The two fields do not share a label
convention: every `custom_820` label carries a bracketed `[code]` suffix, but
only two of `custom_818`'s five labels do — `Z`, `C`, and `U` have none. Both
label sets do start with their code character, so the leading character is the
reliable read for `custom_818`.

Add a CTE between `raced` and the final select:

```sql
    coded as (
        select
            *,

            regexp_extract(homeless_student_pk_12_label, r'\[(\w+)\]') as homeless_c,

            left(homeless_unaccompanied_youth_label, 1) as unaccompanied_c,

            regexp_extract(free_reduced_meals_program_label, r'\[(\w+)\]') as meal_c,
        from raced
    ),
```

Then in the final select, add:

```sql
    -- FLDOE homeless codes describe the student's nighttime residence. Any
    -- residence type means homeless; N is the not-homeless default. The network
    -- domain splits homeless by custody instead, so the separate
    -- unaccompanied-youth field decides Y2 versus Y1. That field is a
    -- five-option select, not a flag -- Y, C and U all mean unaccompanied,
    -- while N means homeless but accompanied and Z means not homeless, so a
    -- null check would mislabel an accompanied homeless student as Y2.
    case
        when homeless_c = 'N'
        then 'N'
        when homeless_c is null
        then null
        when unaccompanied_c in ('Y', 'C', 'U')
        then 'Y2'
        else 'Y1'
    end as homeless_code,

    -- FLDOE residence types mapped to the network primary-nighttime-residence
    -- domain. Awaiting foster care has no analogue and stays null, as does the
    -- not-homeless default.
    case homeless_c
        when 'A'
        then 1
        when 'B'
        then 2
        when 'D'
        then 3
        when 'E'
        then 4
    end as homeless_primary_nighttime_residence_code,

    -- Florida's meal-eligibility element carries both per-student eligibility
    -- and school-level program status. The eligibility codes map onto the
    -- network F/R/P domain; CEP and Provision 2 describe the school's program
    -- rather than the student, so they carry no per-student signal and stay
    -- null. Code 2 is retired upstream (DO NOT USE AFTER 1516).
    case meal_c
        when 'F'
        then 'F'
        when 'D'
        then 'F'
        when 'C'
        then 'F'
        when '9'
        then 'F'
        when '3'
        then 'R'
        when 'E'
        then 'R'
        when 'R'
        then 'R'
        when '1'
        then 'P'
        when '0'
        then 'P'
    end as lunchstatus,
from coded
```

The final select now reads `from coded`, not `from raced` — the `coded` CTE sits
between them.

`is_homeless` reads `homeless_code`, and BigQuery rejects a select-list alias
referenced by another item in the same select list, so it needs its own level.
Turn the existing final `select` into a `conformed` CTE and add a new final
select after it.

The model's full CTE chain ends up as:

```sql
with
    labeled as (...),          -- unchanged, plus the three new label columns
    raced as (...),            -- unchanged
    coded as (... from raced), -- new, from Step 4 above
    conformed as (
        select
            *,
            -- the existing spedlep / gifted_and_talented / lep_status /
            -- ethnicity blocks, plus homeless_code,
            -- homeless_primary_nighttime_residence_code and lunchstatus
        from coded
    )

select
    *,

    -- Matches the formula stg_powerschool__studentcorefields uses, so both SIS
    -- branches agree on what is_homeless means.
    homeless_code in ('Y1', 'Y2') as is_homeless,
from conformed
```

Two edits to the existing file: the current final `select ... from raced`
becomes `conformed as (select ... from coded)`, and the new two-line final
select is appended.

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
uv run dbt test --select test_int_focus__students_homeless_and_meal_conform \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS.

- [ ] **Step 6: Run the whole directory's unit tests**

Run:

```bash
uv run dbt test --select "test_type:unit" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS. Sibling models mock the same `ref()`s, so a column add to
`stg_focus__students` can break their fixtures too. Fix any that fail by adding
the new column to their `given` blocks.

- [ ] **Step 7: Document the four columns**

In `properties/int_focus__students.yml`, add entries. Columns carrying tests
sort to the top of the `columns:` list.

```yaml
- name: homeless_code
  data_type: string
  data_tests:
    - accepted_values:
        arguments:
          values: [N, Y1, Y2]
  description:
    Network homelessness code. N when the student is recorded as not homeless,
    Y2 when homeless and not in a parent or guardian's custody, Y1 when homeless
    otherwise. Null when Focus records nothing.
- name: is_homeless
  data_type: boolean
  description:
    True when homeless_code is Y1 or Y2. Matches the formula the PowerSchool
    staging models use so both SIS branches agree.
- name: homeless_primary_nighttime_residence_code
  data_type: int64
  description:
    Network primary-nighttime-residence code — 1 for shelters and transitional
    housing, 2 for doubled-up, 3 for unsheltered, 4 for hotels or motels. Null
    for students who are not homeless and for those awaiting foster care, which
    has no network analogue.
- name: lunchstatus
  data_type: string
  description:
    Network meal-eligibility code — F for free, R for reduced, P for paid. Null
    where Focus records a school-level program status such as CEP or USDA
    Provision 2, which says nothing about the individual student.
```

- [ ] **Step 8: Build the model and check real values**

Run:

```bash
uv run dbt build --select int_focus__students \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: PASS, including the `accepted_values` test.

Then:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kippmiami_focus'
q = f'''select homeless_code, is_homeless,
homeless_primary_nighttime_residence_code as res, lunchstatus, count(*) as n
from \`teamster-332318.{ds}.int_focus__students\` group by 1,2,3,4'''
for r in c.query(q): print(dict(r))
"
```

Expected today: one row with `homeless_code = 'N'`, `is_homeless = false`,
`res = null`, `lunchstatus = null`, `n` around 3,865, plus a null-everything row
around 124. Every student currently sits at the CEP and not-homeless defaults —
that is the correct current state, and the mapping goes live unchanged when Ops
populates real values.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/focus/models/intermediate/int_focus__students.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__students.yml \
  src/dbt/focus/models/intermediate/unit_tests.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "feat(focus): conform homelessness and meal eligibility to the network domains

Both fields are populated in Focus and decode through the pivot labels,
so the archive's nulls for Miami were a gap in the conform, not missing
data. Meal codes describing the school's CEP or Provision 2 program stay
null because they carry no per-student eligibility.

Refs #4868"
```

---

## Task 4: Seed staging so kipptaf CI sees the new columns

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/intermediate/int_focus__students.sql`
  (comment only)

**Interfaces:**

- Consumes: the widened package `int_focus__students` from Task 3.
- Produces: `zz_stg_kippmiami_focus.int_focus__students` carrying the four new
  columns, and a `state:modified` kipptaf wrapper.

The kipptaf wrapper is an unmodified `union_relations` view, so dbt Cloud CI
defers it to the Staging environment where the new columns do not exist, and
every downstream model fails `Name homeless_code not found`. Two steps close
that.

> **STOP — user authorization required.** The build in Step 2 writes to the
> shared `zz_stg_kippmiami_focus` schema. Ask the user to authorize it in plain
> text before running, and do not proceed without an explicit yes.

- [ ] **Step 1: Force the wrapper `state:modified`**

In `src/dbt/kipptaf/models/focus/intermediate/int_focus__students.sql`, add a
comment above the `with`. A properties-YAML description change does NOT mark a
model modified — it must be a `.sql` edit.

```sql
-- The package model gained homeless_code, is_homeless,
-- homeless_primary_nighttime_residence_code and lunchstatus (#4868). This
-- comment forces state:modified so CI rebuilds the wrapper against the widened
-- staging copy instead of deferring to the narrower Staging environment.
with
```

- [ ] **Step 2: Build the widened model into shared staging**

Run, only after the user authorizes:

```bash
uv run dbt build --select int_focus__students \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kippmiami \
  --target staging
```

Expected: PASS, writing `zz_stg_kippmiami_focus.int_focus__students`.

- [ ] **Step 3: Verify the staging copy carries the new columns**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
c = bigquery.Client(project='teamster-332318')
q = '''select column_name
from \`teamster-332318.zz_stg_kippmiami_focus.INFORMATION_SCHEMA.COLUMNS\`
where table_name = 'int_focus__students'
and column_name in ('homeless_code','is_homeless',
'homeless_primary_nighttime_residence_code','lunchstatus')'''
print(sorted(r['column_name'] for r in c.query(q)))
"
```

Expected: all four names listed. Fewer than four means CI will fail — re-run
Step 2 before continuing.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__students.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "chore(kipptaf): force the focus students wrapper to rebuild in CI

Refs #4868"
```

---

## Task 5: New `int_focus__advisory` at kipptaf

**Files:**

- Create: `src/dbt/kipptaf/models/focus/intermediate/int_focus__advisory.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__advisory.yml`

**Interfaces:**

- Consumes: `int_focus__schedule` (`student_id`, `academic_year`, `schoolid`,
  `course_title`, `course_period_short_name`, `teacher_id`, `course_period_id`)
  and `int_focus__users` (`staff_id`, `first_name`, `last_name`), both already
  wrapped at kipptaf.
- Produces: `int_focus__advisory` at grain
  `(student_number, academic_year, schoolid)` with columns `student_number`
  (`INT64`), `academic_year` (`INT64`), `schoolid` (`INT64`),
  `advisory_section_number` (`STRING`), `advisory_name` (`STRING`),
  `advisor_lastfirst` (`STRING`), `_dbt_source_project` (`STRING`).

Analogue of `int_powerschool__advisory`, matched on course title rather than the
`homeroom` flag — that flag is null on every row of both source models.

- [ ] **Step 1: Write the model**

```sql
-- Miami advisory, the analogue of int_powerschool__advisory. Focus carries a
-- homeroom boolean on both the schedule and the user, but it is null on every
-- row, so the homeroom course is identified by its title instead.
--
-- Elementary only: 957 of 983 ES students carry a Homeroom course for AY2026,
-- against 42 of 593 MS and 0 of 114 HS. int_focus__schedule also holds AY2026
-- alone, so there is no advisory for prior years. Both gaps are Focus
-- configuration, not modeling -- see #4868.
with
    homeroom_enrollments as (
        select
            sch.student_id,
            sch.academic_year,
            sch.schoolid,
            sch.course_period_id,
            sch.course_period_short_name,
            sch._dbt_source_project,

            usr.last_name || ', ' || usr.first_name as advisor_lastfirst,
        from {{ ref("int_focus__schedule") }} as sch
        left join
            {{ ref("int_focus__users") }} as usr
            on sch.teacher_id = usr.staff_id
            and sch._dbt_source_project = usr._dbt_source_project
        where sch.course_title like 'Homeroom%'
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="homeroom_enrollments",
                partition_by="student_id, academic_year, schoolid",
                order_by="course_period_id desc",
            )
        }}
    )

select
    academic_year,
    schoolid,
    advisor_lastfirst,
    _dbt_source_project,

    student_id as student_number,
    course_period_short_name as advisory_section_number,

    coalesce(course_period_short_name, advisor_lastfirst) as advisory_name,
from deduplicate
```

`student_id` on `int_focus__schedule` is the network student number, matching
`int_focus__student_enrollments.network_student_number` — confirm this in Step 3
before trusting the join in Task 6.

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: int_focus__advisory
    description: >-
      One homeroom assignment per Miami student per school year and school,
      conformed to the PowerSchool advisory column names. Focus identifies the
      homeroom by course title because its homeroom flag is unpopulated. Covers
      elementary students only and only the current academic year, because those
      are the only students and years with homeroom course periods scheduled.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
    columns:
      - name: student_number
        description: Network student number for the student in the homeroom.
      - name: academic_year
        description: Academic year of the homeroom enrollment.
      - name: schoolid
        description: Focus school id where the homeroom is scheduled.
      - name: advisory_section_number
        description:
          Short name of the homeroom course period, the Focus analogue of the
          PowerSchool section number.
      - name: advisory_name
        description:
          Display name for the homeroom — the course period short name, falling
          back to the teacher name when the short name is absent.
      - name: advisor_lastfirst
        description:
          Homeroom teacher name in last-comma-first form. Null when the course
          period carries no teacher.
      - name: _dbt_source_project
        description: District code location the row came from.
```

- [ ] **Step 3: Build and verify coverage**

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf
uv run dbt build --select int_focus__advisory \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS, including the uniqueness test.

Then confirm coverage matches the spec's numbers and that the join key is right:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_focus'
q = f'''select e.school_level, count(distinct e.student_number) as n_students,
count(distinct a.student_number) as n_with_advisory
from \`teamster-332318.kipptaf_focus.int_focus__student_enrollments\` as e
left join \`teamster-332318.{ds}.int_focus__advisory\` as a
  on e.student_number = a.student_number
  and e.academic_year = a.academic_year
where e.academic_year = 2026
group by 1'''
for r in c.query(q): print(dict(r))
"
```

Expected: ES around 983 students with around 957 advisories; MS around 593 with
around 42; HS 114 with 0. A zero for ES means the join key is wrong — check
whether `int_focus__schedule.student_id` is prefixed with 8400 and unprefix it
if so.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__advisory.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__advisory.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "feat(kipptaf): add the Miami advisory model from Focus homeroom courses

The Focus homeroom flag is null on every schedule and user row, so the
homeroom is identified by course title. Elementary only, current year
only -- both are Focus configuration gaps, not modeling ones.

Refs #4868"
```

---

## Task 6: New `int_students__student_enrollments`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml`
- Read for reference:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql`

**Interfaces:**

- Consumes: the three NJ district `base_powerschool__student_enrollments`
  sources; `int_focus__student_enrollments`; `int_focus__students` (with Task
  3's columns); `int_focus__advisory` from Task 5.
- Produces: `int_students__student_enrollments` with the same 137-column set
  `base_powerschool__student_enrollments` emits today.

This is the largest task. The model is today's `base_` body with two changes:
the Miami relation leaves the union, and a Focus block joins by
`full union all corresponding`.

- [ ] **Step 1: Copy the existing model body**

```bash
cp /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql \
   /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql
```

- [ ] **Step 2: Drop the Miami relation from the union**

In the new file, delete these four lines from the `union_relations` list:

```sql
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
```

Leave the three NJ `source(...)` entries in place.

- [ ] **Step 3: Add the Focus grade-history CTE**

Insert after the `union_relations` CTE and before `with_region`. `boy_status`
and `is_retained_year` need the prior year's grade, computed over one row per
student-year.

```sql
    -- One row per Miami student per year, carrying the prior year's grade so
    -- boy_status and is_retained_year reproduce the PowerSchool derivation.
    -- rn_year = 1 picks the primary stint, matching the year grain PowerSchool
    -- computes these over.
    focus_year_grain as (
        select
            network_student_number,
            academic_year,
            grade_level,

            lag(grade_level) over (
                partition by network_student_number order by academic_year asc
            ) as grade_level_prev,

            lag(academic_year) over (
                partition by network_student_number order by academic_year asc
            ) as academic_year_prev,
        from {{ ref("int_focus__student_enrollments") }}
        where rn_year = 1
    ),
```

- [ ] **Step 4: Add the Focus conform CTE**

Insert after `focus_year_grain`. Every column name and type must match its NJ
counterpart — `full union all corresponding` matches by name and null-fills what
is absent, but a type mismatch on a shared name is an error.

```sql
    -- Miami enrollment from Focus, conformed to the PowerSchool column names
    -- and value domains so it merges into the NJ branch below by column name.
    -- PowerSchool-only columns -- dcids, NJ state fields, exit_code_kf and
    -- exit_code_ts -- null-fill automatically.
    --
    -- Not conformed, each because Focus has no source rather than because the
    -- values look uniform: is_self_contained and is_out_of_district (no
    -- special-programs equivalent), the exit codes (no KIPP Forward tracking),
    -- and advisor_teachernumber (no network teacher number).
    focus_conformed as (
        select
            enr._dbt_source_relation,
            enr._dbt_source_project,
            enr.region,
            enr.academic_year,
            enr.exitdate,
            enr.enroll_status,
            enr.entrycode,
            enr.exitcode,
            enr.grade_level,
            enr.rn_year,
            enr.year_in_school,
            enr.year_in_network,
            enr.is_enrolled_fdos,
            enr.is_enrolled_oct01,
            enr.is_enrolled_oct15,
            enr.is_enrolled_mar15,
            enr.dob,
            enr.state,
            enr.school_level,
            enr.school_abbreviation,
            enr.reporting_schoolid,

            stu.spedlep,
            stu.lep_status,
            stu.lunchstatus,
            stu.homeless_code,
            stu.is_homeless,
            stu.gifted_and_talented,
            stu.ethnicity,
            stu.gender,
            stu.state_studentnumber,

            adv.advisory_section_number,
            adv.advisory_name,
            adv.advisor_lastfirst,

            enr.ps_schoolid as schoolid,
            enr.startdate as entrydate,
            enr.student_first_name as first_name,
            enr.student_last_name as last_name,
            enr.student_name as lastfirst,
            enr.school as school_name,
            enr.school as reporting_school_name,
            enr.network_student_number as student_number,

            (enr.academic_year + 13) + (-1 * enr.grade_level) as cohort_primary,

            if(yg.grade_level_prev = enr.grade_level, true, false) as is_retained_year,
        from {{ ref("int_focus__student_enrollments") }} as enr
        left join
            {{ ref("int_focus__students") }} as stu
            on enr.network_student_number = stu.student_number
            and enr._dbt_source_project = stu._dbt_source_project
        left join
            focus_year_grain as yg
            on enr.network_student_number = yg.network_student_number
            and enr.academic_year = yg.academic_year
        left join
            {{ ref("int_focus__advisory") }} as adv
            on enr.network_student_number = adv.student_number
            and enr.academic_year = adv.academic_year
            and enr.ps_schoolid = adv.schoolid
    ),
```

- [ ] **Step 5: Add the Focus window CTE**

The remaining derivations are windows over the conformed rows. Insert after
`focus_conformed`.

```sql
    -- Window derivations over the conformed Focus rows, matching the ones the
    -- district base_ model computes for the NJ branch.
    focus_windowed as (
        select
            *,

            max(if(year_in_school = 1, cohort_primary, null)) over (
                partition by student_number, schoolid
            ) as cohort_secondary,

            max(if(year_in_network = 1, schoolid, null)) over (
                partition by student_number
            ) as entry_schoolid,

            max(if(year_in_network = 1, grade_level, null)) over (
                partition by student_number
            ) as entry_grade_level,

            max(is_retained_year) over (
                partition by student_number
            ) as is_retained_ever,
        from focus_conformed
    ),

    -- boy_status and cohort read cohort_secondary, so they follow the window
    -- CTE rather than sharing its select list -- BigQuery rejects a lateral
    -- alias reference.
    focus_final as (
        select
            *,

            case
                when grade_level = 99
                then 'Graduated'
                when year_in_network = 1
                then 'New'
                when grade_level_prev is null
                then 'New'
                when academic_year - academic_year_prev > 1
                then 'Re-Enrolled'
                when grade_level_prev < grade_level
                then 'Promoted'
                when grade_level_prev = grade_level
                then 'Retained'
                when grade_level_prev > grade_level
                then 'Demoted'
            end as boy_status,

            case
                when grade_level >= 9
                then cohort_secondary
                else cohort_primary
            end as cohort,
        from focus_windowed
    ),
```

`focus_conformed` must also project `yg.grade_level_prev` and
`yg.academic_year_prev` for this CTE to read them — add both to its select list
alongside `is_retained_year`.

`cohort` omits the grade-99 arm because Focus carries no graduate placeholders,
so `cohort_graduated` null-fills and the arm would always yield null.

- [ ] **Step 6: Join the two branches**

Change `with_region` to read from the NJ union plus the Focus branch. Replace:

```sql
    with_region as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    )
```

with:

```sql
    powerschool_conformed as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    ),

    with_region as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select * except (grade_level_prev, academic_year_prev),
        from focus_final
    )
```

The `except` drops the two lag helpers, which exist only to derive `boy_status`
and are not part of the output column set.

- [ ] **Step 7: Verify the column set is unchanged**

Run:

```bash
uv run dbt build --select int_students__student_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS.

Then compare against prod's column set:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_students'
q = f'''with n as (select column_name from
\`teamster-332318.{ds}.INFORMATION_SCHEMA.COLUMNS\`
where table_name = 'int_students__student_enrollments'),
o as (select column_name from
\`teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS\`
where table_name = 'base_powerschool__student_enrollments')
select 'only_new' as side, column_name from n where column_name not in (select column_name from o)
union all
select 'only_old', column_name from o where column_name not in (select column_name from n)'''
rows = list(c.query(q))
print('differences:', len(rows))
for r in rows: print(dict(r))
"
```

Expected: `differences: 0`. Any `only_old` column is one the Focus branch
introduced a name collision on or the union dropped — fix before continuing. Any
`only_new` column means a helper leaked into the output.

- [ ] **Step 8: Write the properties YAML**

Copy `base_`'s properties YAML wholesale, then change the model name:

```bash
cp /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__student_enrollments.yml \
   /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml
```

In the copy, change `- name: base_powerschool__student_enrollments` to
`- name: int_students__student_enrollments`, and replace the model description
with:

```yaml
description: |
  Complete enrollment history for every student, across both network SIS
  systems. The three New Jersey regions come from PowerSchool; Miami comes
  from Focus, conformed to the PowerSchool column names and value domains.

  Excludes no-show students, who share an entry and exit date, and students
  with an inactive enrollment status, which PowerSchool uses mainly for
  duplicate records.

  Also carries the demographic data and student identifiers the enrollment
  consumers read. Columns PowerSchool supplies and Focus does not are null
  for Miami — special-program placement, the KIPP Forward exit codes, and
  the advisor teacher number.
```

Update the `homeless_code` column description, which currently ends "Null for
Miami, which does not populate the field", to:

```yaml
description:
  Homelessness code for the enrollment year — N for not homeless, Y1 for
  homeless while in the physical custody of a parent or legal guardian, Y2 for
  homeless and unaccompanied. For the New Jersey regions, read from
  `stg_powerschool__studentcorefields` for the current academic year and from
  `stg_powerschool__s_nj_ren_x` for closed years. For Miami, decoded from the
  Focus homelessness fields in `int_focus__students`.
```

- [ ] **Step 9: Run the model's tests**

Run:

```bash
uv run dbt test --select int_students__student_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS. An `accepted_values` failure on `homeless_code` means the Task 3
mapping produced a value outside N/Y1/Y2.

- [ ] **Step 10: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "feat(kipptaf): add the SIS-neutral enrollment model with a Focus branch

Carries the body base_powerschool__student_enrollments has today, with
the frozen Miami archive dropped from the union and a Focus-conformed
block joined by full union all corresponding. Same 137-column output, so
no downstream contract changes.

Refs #4868"
```

---

## Task 7: Reduce `base_powerschool__student_enrollments` to a passthrough

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__student_enrollments.yml`

**Interfaces:**

- Consumes: `int_students__student_enrollments` from Task 6.
- Produces: the same 137 columns it produces today, for its 15 existing consumer
  sites.

- [ ] **Step 1: Replace the model body**

Replace the entire contents of `base_powerschool__student_enrollments.sql` with:

```sql
-- Compatibility passthrough. The enrollment logic moved to
-- int_students__student_enrollments, which carries both SIS branches; this
-- model exists so the consumers listed in #3999 keep resolving while they
-- migrate. Delete it once they have.
select *,
from {{ ref("int_students__student_enrollments") }}
```

- [ ] **Step 2: Reduce the properties YAML**

Replace the entire contents of the properties YAML with:

```yaml
models:
  - name: base_powerschool__student_enrollments
    description: >-
      Compatibility passthrough over int_students__student_enrollments, which
      holds the enrollment logic and the column documentation. Scheduled for
      removal once its remaining consumers migrate, tracked in #3999. Carries no
      tests of its own — they run on the model underneath, and repeating them
      here would rescan every column for no additional coverage.
```

The tests and 137 column descriptions now live on
`int_students__student_enrollments`.

- [ ] **Step 3: Verify the passthrough is column-identical to prod**

Run:

```bash
uv run dbt build --select base_powerschool__student_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS.

- [ ] **Step 4: Verify every consumer still resolves**

Run:

```bash
uv run dbt build --select base_powerschool__student_enrollments+ --empty \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: PASS across the whole descendant graph. `--empty` proves column
resolution, not values. A `Name <col> not found` here means the Task 6 column
set drifted from prod's — return to Task 6 Step 7.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add \
  src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql \
  src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__student_enrollments.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "refactor(kipptaf): reduce the enrollment base model to a passthrough

Its 15 consumer sites keep resolving unchanged while they migrate to
int_students__student_enrollments under #3999. Tests and column docs
moved to that model rather than being duplicated here.

Refs #4868
Refs #3999"
```

---

## Task 8: Validation sweep

**Files:** none — this task produces evidence, not code.

**Interfaces:**

- Consumes: the built `int_students__student_enrollments`.
- Produces: the numbers that go in the PR body.

Every query runs against the local dev build. Write results to
`.claude/scratch/`, not to any external surface — these touch student-level
rows.

- [ ] **Step 1: NJ parity**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_students'
q = f'''select 'new' as side, count(*) as n_rows,
count(distinct format('%T|%T|%T|%T', student_number, academic_year, entrydate,
_dbt_source_project)) as n_keys
from \`teamster-332318.{ds}.int_students__student_enrollments\`
where _dbt_source_project != 'kippmiami'
union all
select 'prod', count(*),
count(distinct format('%T|%T|%T|%T', student_number, academic_year, entrydate,
_dbt_source_project))
from \`teamster-332318.kipptaf_powerschool.base_powerschool__student_enrollments\`
where _dbt_source_project != 'kippmiami' '''
for r in c.query(q): print(dict(r))
"
```

Expected: identical `n_rows` and `n_keys` on both sides. Any difference means
dropping the Miami relation perturbed NJ, which it must not.

- [ ] **Step 2: Miami AY2026 presence**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_students'
q = f'''select academic_year, school_level, count(*) as n_rows,
count(distinct student_number) as n_students
from \`teamster-332318.{ds}.int_students__student_enrollments\`
where _dbt_source_project = 'kippmiami' and academic_year >= 2025
group by 1, 2'''
for r in c.query(q): print(dict(r))
"
```

Expected: AY2026 present with roughly 1,585 rows, including roughly 114 HS — a
level the archive never carried. Prod returns zero AY2026 Miami rows today.

- [ ] **Step 3: Miami historical reconciliation, AY2018 to AY2025**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_students'
q = f'''with n as (select student_number, academic_year, cohort, boy_status,
homeless_code, school_level
from \`teamster-332318.{ds}.int_students__student_enrollments\`
where _dbt_source_project = 'kippmiami' and academic_year between 2018 and 2025
and rn_year = 1),
o as (select student_number, academic_year, cohort, boy_status, homeless_code,
school_level
from \`teamster-332318.kippmiami_powerschool.base_powerschool__student_enrollments\`
where academic_year between 2018 and 2025 and rn_year = 1)
select
count(*) as n_matched_keys,
countif(n.cohort is distinct from o.cohort) as cohort_diff,
countif(n.boy_status is distinct from o.boy_status) as boy_status_diff,
countif(n.school_level is distinct from o.school_level) as school_level_diff
from n inner join o using (student_number, academic_year)'''
for r in c.query(q): print(dict(r))
"
```

Expected: `n_matched_keys` in the low thousands. `cohort_diff` and
`school_level_diff` should be at or near zero. `boy_status_diff` will be
non-zero where Focus and the archive disagree on a student's first year in
network — investigate any count above a few percent before proceeding.
`homeless_code` is deliberately excluded from the diff: the archive is null for
Miami and Focus now returns `N`, so every row differs by design.

- [ ] **Step 4: Advisory coverage**

Run:

```bash
uv run --with google-cloud-bigquery python -c "
from google.cloud import bigquery
import os
c = bigquery.Client(project='teamster-332318')
ds = 'zz_' + os.environ['USER'] + '_kipptaf_students'
q = f'''select school_level, count(*) as n_rows,
countif(advisory_name is not null) as n_advisory
from \`teamster-332318.{ds}.int_students__student_enrollments\`
where _dbt_source_project = 'kippmiami' and academic_year = 2026
group by 1'''
for r in c.query(q): print(dict(r))
"
```

Expected: ES around 957 populated; MS and HS at or near zero. Assert the ES
count, not a network-wide rate — a network-wide non-null assertion fails by
design.

- [ ] **Step 5: Record the numbers**

Write every result above to `.claude/scratch/4868-validation.md` for the PR
body. Use counts and column names only — no student values.

- [ ] **Step 6: Lint the changed SQL**

Run from inside the worktree — a relative path from the main repo checks the
wrong copies, and `--force` is required or committed files are skipped:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD | grep -E '\.(sql|yml|md)$') </dev/null
```

Expected: no `file:line` findings. If `.trunk/tools/trunk` does not exist, use
`~/.cache/trunk/launcher/trunk`. Unformatted-file findings are fixed by the
pre-commit hook; rule findings must be fixed by hand.

- [ ] **Step 7: Commit any lint fixes**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base commit -m "style(dbt): satisfy sqlfluff on the enrollment models

Refs #4868"
```

Skip this step if Step 6 found nothing.

---

## Task 9: Ops issues, push, and PR

**Files:** none.

**Interfaces:**

- Consumes: `.claude/scratch/4868-validation.md` from Task 8.
- Produces: two GitHub issues and one pull request.

- [ ] **Step 1: File the homeroom scheduling issue**

Use `mcp__github__issue_write` with `method: create`, labels
`["fix", "focus", "kippmiami", "ops-tracked"]`, title
`fix(focus): homeroom course periods are only scheduled for Miami elementary`.
Body states: the Focus `homeroom` flag is null on all 18,789 AY2026
`int_focus__schedule` rows and all 2,183 `int_focus__users` rows; only ES has
Homeroom-titled course periods, so `int_focus__advisory` resolves 957 of 1,690
AY2026 students; the archive covered Miami ES and MS at roughly 99%, so MS
advisory reporting is a live regression; either scheduling homeroom course
periods for MS and HS or populating the `homeroom` flag fixes it with no code
change. Reference `Refs #4868`.

- [ ] **Step 2: File the homelessness field issue**

Use `mcp__github__issue_write` with `method: create`, labels
`["fix", "focus", "kippmiami", "ops-tracked"]`, title
`fix(focus): confirm the Miami homeless unaccompanied youth field is maintained`.
Body states: `custom_820` labels `N` as a default and its options describe
residence type rather than custody; `custom_818` Homeless Unaccompanied Youth is
the only field separating the network `Y2` code from `Y1` and carries one
populated row; ask the Miami team to confirm it is being maintained. Reference
`Refs #4868`.

- [ ] **Step 3: Verify both issue bodies stored correctly**

Run `gh api repos/TEAMSchools/teamster/issues/<n> --jq .body` for each and
confirm the text is intact. The GitHub MCP write tools strip `<...>` tokens and
entity-encode `&` and `"`.

- [ ] **Step 4: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-enrollment-base push
```

Expected: the pre-push trunk hook passes. If it blocks, fix the findings and
re-push rather than bypassing.

- [ ] **Step 5: Open the PR**

Use `.github/pull_request_template.md` as the body. Include the Task 8 numbers,
the ES-only advisory limitation, and the known effects: Miami historical
enrollment dates shift for roughly 1,421 stints, and #4803 orphan counts rise
while staying `severity: warn`. Reference `Closes #4868`, `Refs #4729`,
`Refs #4811`, `Refs #3999`, plus the two Ops issue numbers.

Do NOT `gh project item-add` the PR — it appears on the board via the issue
references.

- [ ] **Step 6: Watch CI**

Both surfaces must be checked: dbt Cloud is a commit status, Trunk and CodeQL
and `claude` are check runs.

```bash
gh pr checks <n> --json name,bucket,state
```

If dbt Cloud fails on `Name <col> not found` against `zz_stg_kippmiami_focus`,
Task 4's staging seed did not take — re-run Task 4 Step 2 and trigger a fresh
build, not `dbt retry`, which replays stale compiled SQL.

After CI passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before calling
it done.

---

## Self-Review

**Spec coverage:**

| Spec item                                                   | Task |
| ----------------------------------------------------------- | ---- |
| `stg_focus__students` gains `custom_818`                    | 1    |
| `int_focus__students__pivot` decodes it                     | 2    |
| Package `int_focus__students` conforms 4 columns            | 3    |
| Homelessness decode incl. Y1/Y2 split                       | 3    |
| Meal eligibility decode                                     | 3    |
| Cross-project staging seed + `state:modified`               | 4    |
| New `int_focus__advisory`, ES only                          | 5    |
| New `int_students__student_enrollments`                     | 6    |
| `cohort_primary` / `_secondary` / `cohort`                  | 6    |
| `boy_status`                                                | 6    |
| `entry_schoolid` / `entry_grade_level` / `is_retained_ever` | 6    |
| Straight-projection columns                                 | 6    |
| Null-filled columns (automatic via corresponding)           | 6    |
| `base_` becomes a passthrough                               | 7    |
| Tests and docs move off `base_`                             | 6, 7 |
| NJ parity                                                   | 8    |
| Miami historical reconciliation                             | 8    |
| Miami AY2026 presence incl. HS                              | 8    |
| Advisory coverage assertion                                 | 8    |
| Consumer resolution (`--empty`)                             | 7    |
| Uniqueness test                                             | 6    |
| Two Ops follow-ups                                          | 9    |

`rpt_gsheets__student_contact_info` reporting Miami at AY2026 is covered
transitively by Task 7 Step 4 plus Task 8 Step 2; it is a view over
`int_extracts__student_enrollments`, so it carries Miami once the base model
does.

**Type consistency:** `student_number` is `INT64` on both branches; `schoolid`,
`cohort*`, `entry_*`, `reporting_schoolid` are `INT64`; `is_*` are `BOOL`;
`homeless_code`, `lunchstatus`, `spedlep`, `advisory_*`, `school_*` are
`STRING`; `lep_status` is `BOOL`; `entrydate` / `exitdate` / `dob` are `DATE`.
Verified against `kippnewark_powerschool.base_powerschool__student_enrollments`.

**Known gap:** Task 6 Step 5 requires `focus_conformed` to project
`grade_level_prev` and `academic_year_prev`, and Step 6 drops them with
`except`. The implementer must add them in Step 4's select list — the step text
says so explicitly, but it is the easiest thing in this plan to miss.
