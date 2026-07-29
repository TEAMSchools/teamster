# DeansList Family Contacts — Add Emergency Contacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add emergency contacts to the DeansList `contacts.txt` feed, numbered
`Emergency 1`–`Emergency 4` in the `Relationship` column, while the primary
parent keeps its real relationship.

**Architecture:** One kipptaf-only reporting view change. Drop the
`contact_slot = 'contact_1'` filter in `rpt_deanslist__family_contacts` so all
Finalsite contact slots flow through, and derive the `Relationship` value from
`contact_slot`. Swap the row-grain uniqueness test to
`(StudentID, Relationship)`. A new dbt unit test drives the change (TDD).

**Tech Stack:** dbt (BigQuery), dbt_utils, dbt unit tests, trunk (sqlfluff +
prettier + yamllint).

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts`.
  Every `git`, `dbt`, Read/Edit/Write path targets that worktree.
- Issue: [#4478](https://github.com/TEAMSchools/teamster/issues/4478). Spec:
  `docs/superpowers/specs/2026-07-21-deanslist-emergency-contacts-design.md`.
- Nine DeansList template columns only — do NOT add a tenth column to the feed.
  `contact_slot` is used only inside the `Relationship` `CASE`; it is not
  projected.
- SQL follows `src/dbt/CLAUDE.md`: BigQuery dialect, trailing commas, single
  quotes, max one level of function nesting, no `QUALIFY`/`ORDER BY`,
  backtick-quoted output aliases, computed values derived as named CTE columns.
- YAML `description:` scalars must not contain `": "` (colon-space) or start
  with a backtick. Unit-test `given`/`expect` scalars stay UNQUOTED unless a
  quote is needed to preserve the string type.
- `uv run` for all dbt; never bare `dbt`. Do not run `trunk fmt`/`trunk check`
  by hand except the explicit `trunk check` step below.

---

## File structure

- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
  — the reporting view. Drops the slot filter; adds the numbered-`Relationship`
  `CASE`; renames the `parent_contacts` CTE to `contacts`.
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`
  — swaps the `StudentID` `unique` test for a model-level
  `unique_combination_of_columns([StudentID, Relationship])` (error), updates
  the model + `Relationship` descriptions, and adds the unit test.

No other files. All upstream columns already exist in prod, so there is no
district, source-schema, staging-seed, or Dagster/Python change.

---

## Task 1: Add emergency contacts, numbered and grain-tested

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`

**Interfaces:**

- Consumes (unchanged, already in prod): `int_finalsite__student_contacts`
  (`finalsite_enrollment_id`, `_dbt_source_project`, `contact_slot`,
  `relationship`, `contact_first_name`, `contact_last_name`, `email`,
  `phone_home`, `phone_work`, `phone_mobile`);
  `int_finalsite__contact_id_attributes` (`finalsite_enrollment_id`,
  `_dbt_source_project`, `powerschool_student_number`);
  `stg_powerschool__students` (`student_number`, `enroll_status`,
  `_dbt_source_relation`).
- Produces: the `contacts.txt` feed shape — columns `StudentID` (int64),
  `ParentFirstName`, `ParentLastName`, `HomePhone`, `WorkPhone`, `CellPhone`,
  `Email`, `Relationship`, `Language` (all string). Grain: one row per
  `(StudentID, Relationship)`.

- [ ] **Step 1: Add the failing unit test to the properties yml**

Append this `unit_tests:` block to the end of
`src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`
(top-level key, sibling of `models:`):

```yaml
unit_tests:
  - name: test_family_contacts_emergency_numbering
    description:
      One student with a primary parent plus two emergency contacts. Asserts the
      primary parent keeps its Finalsite relationship, each emergency slot is
      relabeled Emergency N by slot number, and all three contacts are emitted
      for the enrolled student.
    model: rpt_deanslist__family_contacts
    given:
      - input: ref('int_finalsite__student_contacts')
        format: sql
        rows: |
          select
            'enr-001' as finalsite_enrollment_id,
            'kippnewark' as _dbt_source_project,
            'contact_1' as contact_slot,
            'parent' as relationship,
            'Alice' as contact_first_name,
            'Johnson' as contact_last_name,
            'alice@example.com' as email,
            '305-555-0100' as phone_home,
            cast(null as string) as phone_work,
            '305-555-0101' as phone_mobile
          union all
          select
            'enr-001', 'kippnewark', 'emergency_1', 'grandparent',
            'Bob', 'Smith', cast(null as string), cast(null as string),
            cast(null as string), '305-555-0200'
          union all
          select
            'enr-001', 'kippnewark', 'emergency_2', 'aunt',
            'Carol', 'Diaz', cast(null as string), cast(null as string),
            cast(null as string), cast(null as string)
      - input: ref('int_finalsite__contact_id_attributes')
        format: sql
        rows: |
          select
            'enr-001' as finalsite_enrollment_id,
            'kippnewark' as _dbt_source_project,
            '123456' as powerschool_student_number
      - input: ref('stg_powerschool__students')
        format: sql
        rows: |
          select
            123456 as student_number,
            0 as enroll_status,
            'kippnewark_powerschool' as _dbt_source_relation
    expect:
      rows:
        - {
            StudentID: 123456,
            ParentFirstName: Alice,
            ParentLastName: Johnson,
            Relationship: parent,
            HomePhone: 305-555-0100,
            CellPhone: 305-555-0101,
            Email: alice@example.com,
          }
        - {
            StudentID: 123456,
            ParentFirstName: Bob,
            ParentLastName: Smith,
            Relationship: Emergency 1,
            CellPhone: 305-555-0200,
          }
        - {
            StudentID: 123456,
            ParentFirstName: Carol,
            ParentLastName: Diaz,
            Relationship: Emergency 2,
          }
```

Rationale for `format: sql` on every input: it provides exactly the columns the
model reads and avoids dbt schema introspection of the real relations (per
`src/dbt/CLAUDE.md`). Columns omitted from an `expect` row are compared as null.
The `_dbt_source_relation` value `kippnewark_powerschool` makes
`extract_code_location` resolve to `kippnewark`, matching the finalsite rows'
`_dbt_source_project`.

- [ ] **Step 2: Ensure worktree deps, then run the unit test to verify it
      fails**

The current model still filters `contact_slot = 'contact_1'`, so the two
emergency rows drop and the model returns one row against three expected.

Run:

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts/src/dbt/kipptaf

uv run dbt test \
  --select "rpt_deanslist__family_contacts,test_type:unit" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL — the unit test reports a row-count / value difference (1 actual
row vs 3 expected). If instead it errors on profiles, add
`--profiles-dir /workspaces/teamster/.dbt`.

- [ ] **Step 3: Rewrite the model SQL**

Replace the entire contents of
`src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
with:

```sql
with
    contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc.phone_home,
            sc.phone_work,
            sc.phone_mobile,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,

            case sc.contact_slot
                when 'emergency_1'
                then 'Emergency 1'
                when 'emergency_2'
                then 'Emergency 2'
                when 'emergency_3'
                then 'Emergency 3'
                when 'emergency_4'
                then 'Emergency 4'
                else sc.relationship
            end as relationship,
        from {{ ref("int_finalsite__student_contacts") }} as sc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on sc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and sc._dbt_source_project = xw._dbt_source_project
        where
            sc._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and xw.powerschool_student_number is not null
    ),

    enrolled_students as (
        select
            student_number,

            {{ extract_code_location("stg_powerschool__students") }}
            as _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0
    )

select
    c.student_number as `StudentID`,
    c.contact_first_name as `ParentFirstName`,
    c.contact_last_name as `ParentLastName`,
    c.phone_home as `HomePhone`,
    c.phone_work as `WorkPhone`,
    c.phone_mobile as `CellPhone`,
    c.email as `Email`,
    c.relationship as `Relationship`,

    cast(null as string) as `Language`,
from contacts as c
inner join
    enrolled_students as s
    on c.student_number = s.student_number
    and c._dbt_source_project = s._dbt_source_project
```

Changes vs. the current file: `contact_slot = 'contact_1'` filter removed; `CTE`
renamed `parent_contacts` → `contacts` and its alias `pc` → `c`; the passthrough
`sc.relationship` replaced by the `CASE`. (sqlfmt will collapse the
`when … then …` lines at commit; either layout is acceptable.)

- [ ] **Step 4: Update the properties yml — uniqueness test and descriptions**

In
`src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`:

Replace the model `description` (lines 3–9 in the current file) with:

```yaml
description:
  DeansList nightly Family Contacts import (`contacts.txt`) for the NJ regions —
  one row per Finalsite contact for each currently enrolled student, covering
  the primary parent (`contact_1`, the relationship flagged primary, falling
  back to financial) plus emergency contacts (`emergency_1` through
  `emergency_4`). Emergency contacts carry a numbered `Emergency N` relationship
  so Ops can exclude them from DeansList guardian messaging; the primary parent
  keeps its real Finalsite relationship. Column names match the DeansList import
  template headers exactly. Delivered by the Dagster asset
  `kipptaf/extracts/deanslist/contacts_txt`.
```

Immediately after the model `description` and before `columns:`, add the
model-level grain test:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - StudentID
          - Relationship
      config:
        severity: error
```

On the `StudentID` column, remove the `unique` test but keep `not_null` (error).
The column's `data_tests:` becomes:

```yaml
data_tests:
  - not_null:
      config:
        severity: error
```

Replace the `Relationship` column `description` with:

```yaml
description:
  Relationship of the contact to the student. For the primary parent
  (`contact_1`) this is the Finalsite `rel_type` (`parent`, `stepparent`,
  `guardian`, `grandparent`, etc.). For emergency contacts this is `Emergency
  N`, numbered by the Finalsite emergency slot (`emergency_1` through
  `emergency_4`).
```

Leave `ParentFirstName`, `ParentLastName`, phones, `Email`, and `Language`
columns and their tests unchanged (`ParentLastName` `not_null` stays at the
project-default warn).

- [ ] **Step 5: Run the unit test to verify it passes**

Run:

```bash
uv run dbt test \
  --select "rpt_deanslist__family_contacts,test_type:unit" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS (1 unit test).

- [ ] **Step 6: Build the view against prod data and run the data tests**

Run:

```bash
uv run dbt build \
  --select rpt_deanslist__family_contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: the view builds in the dev schema and every test PASSES — in
particular `unique_combination_of_columns(StudentID, Relationship)` (error) and
`not_null` on `StudentID` (error). `ParentLastName` `not_null` may WARN (~8
rows); that is expected and acceptable.

- [ ] **Step 7: Confirm the built view's shape (row count and grain)**

Query the dev-built view via the BigQuery MCP (schema is
`zz_<github_user>_kipptaf_extracts`; find it with the SCHEMATA query in
`src/dbt/CLAUDE.md` if unsure). Confirm ~30,478 rows, that `Relationship`
`Emergency N` values appear, and `(StudentID, Relationship)` is unique
(`count(*) = count(distinct format('%T|%T', StudentID, Relationship))`). Do not
copy any PII values into the commit, PR, or issue.

- [ ] **Step 8: Lint the changed files**

Run (from inside the worktree; the `trunk` binary lives only in the main repo):

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml \
  </dev/null
```

Expected: No issues (sqlfluff, yamllint, prettier). Fix any findings inline and
re-run.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts \
  add \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml

git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-emergency-contacts \
  commit -m "feat(deanslist): add emergency contacts to family contacts export

Closes #4478"
```

---

## Post-implementation

- Push the branch and open a PR with `.github/pull_request_template.md` as the
  body; the PR body should `Closes #4478`.
- dbt Cloud CI rebuilds the `rpt` view under `state:modified+`. After CI passes,
  fetch warnings with `get_job_run_error(warning_only=true)` — a
  `ParentLastName` `not_null` warn (~8 rows) is expected, not a regression.
- Post-merge: Dagster rematerializes the view and the `contacts_txt` extract
  asset emits the wider `contacts.txt` on the next nightly run.

## Self-review notes

- **Spec coverage:** drop filter (Step 3), numbered `Emergency N` (Step 3 CASE),
  `(StudentID, Relationship)` error-level uniqueness (Step 4), `ParentLastName`
  stays warn (Step 4), descriptions updated (Step 4), kipptaf-only single PR
  (file structure). All covered.
- **No placeholders:** every step has exact paths, code, commands, expected
  output.
- **Type consistency:** `StudentID` int64 (from `safe_cast(... as int64)`);
  `Relationship` string (CASE branches + `rel_type` are all string); unit-test
  `powerschool_student_number` supplied as string `'123456'` and cast to
  `123456`.
