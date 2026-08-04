# Survey Dashboard department gate implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scope Survey Dashboard support responses to the department each
question rates, and remove respondent names from every support view.

**Architecture:** The question-to-department mapping is data, carried on the
existing `src_google_sheets__google_forms__form_items_extension` sheet through
`int_surveys__survey_responses` to `rpt_tableau__survey_responses`. The
group-to-department authorization is a Tableau calculated field, because
`ISMEMBEROF()` takes only a literal group name. Neither half works without the
other, but the data half ships first and is inert until the workbook uses it.

**Tech Stack:** dbt (BigQuery, kipptaf project), Google Sheets external table,
Tableau Desktop / Tableau Cloud.

Design:
`docs/superpowers/specs/2026-08-04-survey-dashboard-department-gate-design.md`

**Status:** Tasks 2, 3 and 4 shipped in PR #4728. Task 1 (the sheet) and Task 5
(re-staging the external) are the immediate blockers — nothing built until they
land. Tasks 6 through 10 follow.

## Global Constraints

- Target project is `kipptaf`. Every dbt command runs through `uv run`, never a
  bare `dbt`.
- New column names, verbatim: `rated_department_code`, `rated_department_name`.
  Both `string`.
- The sheet's declared `columns:` bind **positionally** after
  `skip_leading_rows: 1`. Both new columns go at the END of the sheet and at the
  END of the `columns:` list, in the same order.
- The source's `sheet_range` is the named range
  `src_google_forms__form_items_extension`, which spans A:F today. It must be
  widened to A:H or BigQuery never sees the new columns.
- `abbreviation` is not unique in the sheet — 356 populated rows, 309 distinct
  abbreviations, 33 abbreviations on more than one row. Never join it to
  response rows without projecting to one row per abbreviation first.
- `abbreviation` is nullable by design: section-header rows carry a `Title` and
  no abbreviation, and the sheet's unbounded named range yields ~478 fully null
  phantom rows. Do not add `not_null` to it.
- No `ORDER BY`, no `QUALIFY`, no subqueries against tables or CTEs, max one
  level of function nesting, trailing commas in every `SELECT`. See
  `src/dbt/CLAUDE.md` → SQL conventions.
- PII stays local. Respondent names and survey free text never appear in a
  commit, PR, issue, or comment.

---

### Task 1: Add the two columns to the Google Sheet

**Owner:** Ops / the user. No repo change. Nothing downstream works until this
lands, and the dbt tasks below will fail their build until it does.

**Files:** none. Google Sheet `1OvJ95fuDCWVu9YQoVZnjauC8mdpgL4BmqdfqvgT7gAw`,
tab `Form Items Extension`.

- [ ] **Step 1: Append two header cells**

In row 1, set `G1` to `Rated Department Code` and `H1` to
`Rated Department Name`. Column F is `URL ID` — the new columns go after it,
with no blank column between.

- [ ] **Step 2: Widen the named range**

The named range `src_google_forms__form_items_extension` currently covers
columns A through F. Extend it to A through H: Data → Named ranges →
`src_google_forms__form_items_extension` → edit the range to
`'Form Items Extension'!A:H`.

- [ ] **Step 3: Leave the value cells empty for now**

Populating the codes is Task 6, which is blocked on the taxonomy decision. An
empty column is the correct interim state: every code reads null, which the
design routes to the restricted default.

- [ ] **Step 4: Confirm the range**

Re-open Data → Named ranges and read the range back. It must say `A:H`, not
`A1:H` or `A:F`.

---

### Task 2: Declare the columns on the source and the staging contract

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (the
  `src_google_sheets__google_forms__form_items_extension` block, after the
  `url_id` column entry)
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__google_forms__form_items_extension__one_department_per_abbreviation.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: the two sheet columns from Task 1.
- Produces:
  `stg_google_sheets__google_forms__form_items_extension.rated_department_code`
  and `.rated_department_name`, both `string`, both nullable, with at most one
  distinct `(code, name)` pair per `abbreviation`.

- [x] **Step 1: Add the two columns to the source**

Append to the `columns:` list of
`src_google_sheets__google_forms__form_items_extension`, after `url_id`:

```yaml
- name: rated_department_code
  data_type: string
- name: rated_department_name
  data_type: string
```

- [x] **Step 2: Add the two columns to the staging properties**

Append to the `columns:` list. The staging model is `select *,` so its SQL is
untouched; the contract is what needs the declaration.

```yaml
- name: rated_department_code
  data_type: string
  description: >-
    Stable snake_case code for the department this question rates, hand-entered
    by Ops. Blank or null on questions that rate no department, which the Survey
    Dashboard routes to its most restricted audience. Several question
    abbreviations may share one code -- that is how departments that have merged
    are expressed.
- name: rated_department_name
  data_type: string
  description: >-
    Display label for rated_department_code, hand-entered by Ops. Presentation
    only; authorization matches on the code.
```

- [x] **Step 3: Write the functional-dependency test**

`int_surveys__survey_responses` projects the mapping to one row per
`abbreviation` with `distinct`. That is only a projection if every row sharing
an abbreviation carries the same `(code, name)` **pair** — `distinct` keys on
every projected column, so two rows agreeing on the code but differing in
display name survive it and fan the join out just as surely as a wrong code. The
test asserts one distinct pair per abbreviation, not one distinct code.

```sql
with
    sheet_rows as (
        select
            format(
                '%T|%T', rated_department_code, rated_department_name
            ) as department_mapping,

            lower(abbreviation) as abbreviation,
        from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
        where abbreviation is not null
    ),

    department_mappings as (
        select
            abbreviation,

            count(distinct department_mapping) as distinct_department_mappings,
        from sheet_rows
        group by abbreviation
    )

select *,
from department_mappings
where distinct_department_mappings > 1
```

`format('%T|%T', ...)` rather than `concat()` — `concat` returns null when any
argument is null and would silently miscount violations while the columns are
still sparsely populated.

Do **not** add `not_null` to `abbreviation` here. Roughly 525 of 881 staged rows
have a null abbreviation — section headers carry a `Title` and no abbreviation,
and the row-unbounded named range yields several hundred phantom rows — so the
test would fail on day one. The `where abbreviation is not null` filters above
are the intended handling.

- [x] **Step 4: Register the test's description**

Append to `src/dbt/kipptaf/tests/properties.yml`:

```yaml
- name: stg_google_sheets__google_forms__form_items_extension__one_department_per_abbreviation
  description: >-
    The sheet's grain is (form_id, item_id), so the same question abbreviation
    recurs across survey forms and years -- dozens of abbreviations sit on more
    than one row. int_surveys__survey_responses projects the mapping to one row
    per abbreviation with distinct before joining it to response rows, which is
    a grain projection only while every row sharing an abbreviation carries the
    same (rated_department_code, rated_department_name) pair. The pair is what
    distinct keys on, so drift in EITHER column breaks the projection -- a
    display-text tweak or re-casing applied to one occurrence of an abbreviation
    does it just as surely as a wrong code. Distinct then duplicates instead of
    deduplicating, fanning out survey responses and breaking the response-grain
    uniqueness test downstream. This test fails loudly on any abbreviation
    carrying more than one distinct pair.
  config:
    severity: error
    meta:
      dagster:
        ref:
          name: stg_google_sheets__google_forms__form_items_extension
```

- [x] **Step 5: Parse**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target prod` Expected:
parses clean, no warnings naming either new column.

- [x] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/sources-external.yml \
  src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml \
  src/dbt/kipptaf/tests/stg_google_sheets__google_forms__form_items_extension__one_department_per_abbreviation.sql \
  src/dbt/kipptaf/tests/properties.yml
git commit -m "feat(dbt): carry the rated department on the form items extension sheet"
```

---

### Task 3: Carry the mapping through `int_surveys__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`

**Interfaces:**

- Consumes:
  `stg_google_sheets__google_forms__form_items_extension.rated_department_code`
  / `.rated_department_name` from Task 2.
- Produces: the same two columns on `int_surveys__survey_responses`, one value
  per response row, null where the question is absent from the sheet.

- [x] **Step 1: Add the mapping CTE**

Insert after the `enriched` CTE's closing paren, before the final `select`. The
`distinct` is load-bearing and annotated, per the SQL conventions. Plain columns
come before the `lower()` expression — ST06 orders simple functions after column
enumerations, and sqlfluff fails the reverse.

```sql
    question_departments as (
        /* grain projection: the code/name pair a question rates is a property of
           the question shortname, not of the form it appeared on, so the sheet's
           (form_id, item_id) rows collapse to one row per shortname. Distinct
           keys on the pair, so drift in either column would fan this out -- the
           one_department_per_abbreviation singular test guards against both. */
        select distinct
            rated_department_code,
            rated_department_name,

            lower(abbreviation) as question_shortname,
        from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
        where abbreviation is not null
    ),

    enriched_keyed as (
        select *, lower(question_shortname) as question_shortname_key, from enriched
    )
```

- [x] **Step 2: Rewrite the final select**

`question_shortname_key` exists only to keep the join predicate free of
one-sided calculations, so it is dropped from the output. `question_shortname`
itself keeps its original case — consumers depend on that.

```sql
select
    e.* except (question_shortname_key),

    qd.rated_department_code,
    qd.rated_department_name,

    coalesce(
        cast(e.respondent_employee_number as string), e.respondent_email
    ) as respondent_identifier,
from enriched_keyed as e
left join question_departments as qd on e.question_shortname_key = qd.question_shortname
```

- [x] **Step 3: Document the two columns**

Append to the `columns:` list in the properties yml:

```yaml
- name: rated_department_code
  data_type: string
  description: >-
    Code for the department this question rates, joined from the form items
    extension sheet on the lowered question shortname. Null when the question
    rates no department or is absent from the sheet; the Survey Dashboard treats
    both the same way.
- name: rated_department_name
  data_type: string
  description: >-
    Display label for rated_department_code.
```

- [x] **Step 4: Parse and compile**

Run:

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --target prod
uv run dbt compile --select int_surveys__survey_responses \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: both succeed. Read
`src/dbt/kipptaf/target/compiled/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
and confirm the `except (question_shortname_key)` survived and the join is on
plain columns.

- [x] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql \
  src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml
git commit -m "feat(dbt): join the rated department onto survey responses"
```

---

### Task 4: Pass the columns through to Tableau

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_responses.yml`

**Interfaces:**

- Consumes: the two columns on `int_surveys__survey_responses` from Task 3.
- Produces: `rated_department_code` / `rated_department_name` on the
  contract-enforced `rpt_tableau__survey_responses`, which is what the workbook
  extract reads.

- [x] **Step 1: Project the columns**

Add to the `sr.` block, after `sr.round_rn`:

```sql
    sr.rated_department_code,
    sr.rated_department_name,
```

- [x] **Step 2: Add the contract entries**

The model is contract-enforced, so an undeclared column fails the build. Append
to the `columns:` list:

```yaml
- name: rated_department_code
  data_type: string
  description: >-
    Code for the department a support-survey question rates. The Survey
    Dashboard's RLS - Department Gate matches group membership against this
    column; null or blank reaches only the all-access and cross-department
    branches.
- name: rated_department_name
  data_type: string
  description: >-
    Display label for rated_department_code.
```

- [x] **Step 3: Parse and compile**

Run:

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --target prod
uv run dbt compile --select rpt_tableau__survey_responses \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: both succeed, and the compiled SQL lists both columns.

- [x] **Step 4: Lint**

Run from inside the worktree, since the `--force` check resolves paths against
the cwd:

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD) </dev/null
```

Expected: no `sqlfluff` or `yamllint` findings on the changed files.

- [x] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_responses.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_responses.yml
git commit -m "feat(dbt): publish the rated department to the Tableau survey extract"
```

---

### Task 5: Stage the external and build the chain

**Owner:** the user. `stage_external_sources --target staging` drops and
recreates a shared `zz_stg` table, so it is authorization-gated and cannot be
run by an agent. dbt Cloud CI never runs it, which is why CI cannot pass on
Tasks 2 through 4 until this happens.

**Files:** none.

- [ ] **Step 1: Recreate the staging external**

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__google_forms__form_items_extension" \
  --vars '{ext_full_refresh: true}' --target staging --project-dir src/dbt/kipptaf
```

The selector is `<source_name>.<table_name>` — not project-qualified.
`ext_full_refresh: true` is required; without it an existing table is skipped
and the new columns never appear.

- [ ] **Step 2: Build the chain**

```bash
uv run dbt build --select stg_google_sheets__google_forms__form_items_extension+ \
  --project-dir src/dbt/kipptaf --target staging
```

Expected: the staging model, `int_google_forms__form__items`,
`int_surveys__survey_responses`, `rpt_tableau__survey_responses`, and
`fct_survey_responses` all build, and the new functional-dependency test passes
(trivially, while the column is empty).

- [ ] **Step 3: Confirm the join added no rows**

Compare against prod, which does not yet have the join:

```sql
select
  (select count(*) from `teamster-332318.zz_stg_kipptaf_tableau.rpt_tableau__survey_responses`) as staged_rows,
  (select count(*) from `teamster-332318.kipptaf_tableau.rpt_tableau__survey_responses`) as prod_rows
```

Expected: equal. A staged count that is a multiple of prod means the mapping
fanned out — the `distinct` is not holding, so re-check Task 2's test.

---

### Task 6: Populate the department taxonomy and pin it with a test

**Owner:** Ops, with the data team. **Blocked on open question 1** in the spec:
merged departments must resolve to one code, and the SUP-side `cmo_*` /
`regional_*` scopes need a decision — one code per department, or separate codes
per scope.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml`

- [ ] **Step 1: Fill in the sheet**

For every abbreviation that rates a department, enter the agreed code in column
G and its label in column H. Leave both blank on `open_ended_*`, `*_overall_*`,
`supplies`, `respondent_name`, `school_based`, and every section header. Two
abbreviations break their own naming scheme and must be entered by hand rather
than pattern-filled: `sre_oe` belongs with `student_recruitment_*`, and
`teaching_and_learning_oe` belongs with `teaching_learning_*`.

An abbreviation on more than one row must get the **same code AND the same
name** on every one of its rows — the display label is part of what makes the
mapping one row per abbreviation, so a differing name fans out survey responses
even when the code matches. Copy the pair down rather than retyping it. Task 2's
test fails on any drift, but catching it in the sheet is cheaper than catching
it in a failed build.

- [ ] **Step 2: Pin the agreed list**

Add an `accepted_values` test to `rated_department_code`, replacing the
placeholder list with the agreed codes. `accepted_values` passes nulls, so the
blank case needs no entry:

```yaml
data_tests:
  - accepted_values:
      arguments:
        values:
          - advocacy
          - compliance
          - data
          # ... one entry per agreed code
      config:
        severity: error
```

- [ ] **Step 3: Verify nothing fanned out**

Re-run Task 5 Step 2 and Step 3. The functional-dependency test is now doing
real work — a code entered inconsistently across two rows sharing an
abbreviation fails it.

---

### Task 7: Tableau remediation slice

**Owner:** the user, in Tableau Desktop. Independent of Tasks 1 through 6 and
shippable before them. Every item narrows access or deletes dead code.
Authoritative calc text: `docs/guides/tableau-permissions.md`.

**Files:** the Survey Dashboard workbook.

- [ ] **Step 1: Protect `support_open_ended`**

It is the only support sheet with neither the respondent filter nor the
small-cell suppression. Add `Permissions - Support` (set to TRUE) and
`COUNTD(employee_number) >= 4` to its filter shelf, matching the four other
support sheets.

- [ ] **Step 2: Scope the blanket KTAF grant**

In `Permissions - Support`, the branch granting unconditionally to
`KNJ-SG-Tableau All Staff KTAF` becomes region-scoped, matching the entity gate
in the permissions guide. Central office staff keep access to their own regions,
not to everything.

- [ ] **Step 3: Delete `Permissions - Support (Preview)`**

A dead four-line field holding an individual by-name grant. Confirm no sheet
filters on it before deleting — resolve by internal name, not caption, since a
filter's `column` attribute never updates on rename.

- [ ] **Step 4: Remove `KNJ-SG-Tableau The Syndicate`**

Delete the branch wherever it appears in the support permissions fields.

- [ ] **Step 5: Apply the #4656 renames**

`legal_entity` becomes `home_business_unit_name`, `location` becomes
`location_clean_name`, `department` becomes `home_department_name`. The workbook
still uses the pre-#4656 names.

- [ ] **Step 6: Publish and spot-check**

Publish, then use Preview as User on one central-office persona to confirm the
region scoping took effect and no sheet broke on the renames.

---

### Task 8: Build `RLS - Department Gate`

**Owner:** the user, in Tableau Desktop. Requires Task 5 (the column must exist
in the extract) and open questions 2 and 3 from the spec (the `IN` lists and
which departments get groups).

**Files:** the Survey Dashboard workbook.

- [ ] **Step 1: Create the field**

A new calculated field named `RLS - Department Gate`, kept separate from
`Permissions - Support`. Both go on the filter shelf set to TRUE, which ANDs
them, and either can be dropped onto a sheet alone to debug a persona.

```text
// all-access
ISMEMBEROF('KNJ-SG-Tableau All Data')
OR ISMEMBEROF('KNJ-SG-Tableau TC')

// cross-department leadership; entity scoping comes from Permissions - Support
OR ISMEMBEROF('KNJ-SG-Tableau All MDSO')
OR ISMEMBEROF('KNJ-SG-Tableau All HOS')

// department-scoped: one branch per group, an IN list per group
OR (ISMEMBEROF('KNJ-SG-Tableau All HR')
    AND [rated_department_code] IN ('human_resources', 'cmo_hroperations'))
// one branch per department that has a group
```

- [ ] **Step 2: Write one branch per department group**

Use the group table in the spec's _Group coverage_ section. Confirm
`KNJ-SG-Tableau All Recruiting` and `KNJ-SG-Tableau All New Teacher Development`
exist before relying on them — both are marked "confirm". Group membership is
not ingested, so no test can assert a group name is real; a typo silently grants
nothing.

- [ ] **Step 3: Do not add `ELSE TRUE`**

The restricted default is reached by falling off the end of the expression. A
row with a blank, null, or group-less code matches no branch and is reachable
only through the all-access and cross-department heads. An `ELSE TRUE` would
invert that and can be added by accident during a later edit — its absence is
the safety property.

- [ ] **Step 4: Apply to all five support sheets**

Add the field to the filter shelf of every support sheet, including
`support_open_ended`. Leave `Question + Job Group Filter` alone — it is a
respondent exclusion filter, not a permission gate.

---

### Task 9: Remove respondent names from the support views

**Owner:** the user, in Tableau Desktop and Tableau Cloud. Decided 2026-08-04:
no support-view viewer sees respondent names, including the rated department.

**Files:** the Survey Dashboard workbook; the workbook's Cloud permissions.

- [ ] **Step 1: Remove the identity fields from every support sheet**

Two fields carry identity: the `respondent_name` column and the
`Teammate (copy)` calculated field that aliases it. Remove both from all five
support sheets — rows, columns, marks, filters, **and tooltips**, which are the
easiest place to leave one behind.

- [ ] **Step 2: Hide both fields in the Data pane**

Right-click each → Hide. Removing without hiding leaves them one drag away from
a support sheet. Do not substitute a conditional wrapper such as
`IF <viewer is departmental> THEN [respondent_name] END` — that keeps the field
live and re-openable.

- [ ] **Step 3: Revoke Download Data and Web Edit**

Tableau has no column-level security, so a viewer holding either capability
reads `respondent_name` straight from the extract no matter what the sheets
show. On the published workbook, revoke both for every group that is not
all-access. **Anonymity is false without this step** — the sheet edits alone do
not deliver it.

- [ ] **Step 4: Verify from the extract side**

With Preview as User on a departmental persona, open a support sheet, then try
View Data on a mark. No respondent name may appear. Repeat with Download → Data.

---

### Task 10: Persona verification

**Owner:** the user, in Tableau Cloud with Preview as User. Runs after Tasks 6
through 9.

**Files:** none.

- [ ] **Step 1: Walk the persona table**

Work the table in the spec's _Testing_ section, one persona at a time. Both
directions are findings: seeing more than expected is a security bug, seeing
less is a broken gate.

- [ ] **Step 2: Check the two edge personas explicitly**

A viewer in no departmental group must see nothing on the support sheets. A
blank-code question must be visible only to all-access and cross-department
viewers. These are the branches with no positive test elsewhere.

- [ ] **Step 3: Re-read `support_open_ended` last**

It began with neither the respondent filter nor the suppression, so it is the
sheet most likely to have been missed by an earlier step. Confirm it carries
`Permissions - Support`, the `COUNTD(employee_number) >= 4` suppression, and
`RLS - Department Gate`, and shows no respondent name.

- [ ] **Step 4: Record what shipped**

Update `docs/guides/tableau-permissions.md` with the Survey Dashboard as a
per-workbook variant, the way the Coaching Conversation Tool release gate is
recorded, and note which naming convention the new departmental groups used.
