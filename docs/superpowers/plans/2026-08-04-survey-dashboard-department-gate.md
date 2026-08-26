# Survey Dashboard department gate implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scope Survey Dashboard support responses to the department each
question rates, and remove respondent names from every support view.

**Architecture:** The question-to-department mapping is data, carried on its own
`src_google_sheets__google_forms__question_department_crosswalk` sheet through
`int_surveys__survey_responses` to `rpt_tableau__survey_responses`. The
group-to-department authorization is a Tableau calculated field, because
`ISMEMBEROF()` takes only a literal group name. Neither half works without the
other, but the data half ships first and is inert until the workbook uses it.

**Tech Stack:** dbt (BigQuery, kipptaf project), Google Sheets external table,
Tableau Desktop / Tableau Cloud.

Design:
`docs/superpowers/specs/2026-08-04-survey-dashboard-department-gate-design.md`

**Status:** Tasks 1 through 6 are done. The crosswalk sheet carries 309
abbreviations with 66 mapped across all 14 agreed department codes, the external
is staged, the chain builds against `staging` with all four crosswalk tests
passing, and the join adds no rows. Open question 1 is resolved — see
_Department taxonomy_ below. Tasks 7 through 10 are Tableau workbook edits,
blocked until this merges because the calculated fields cannot reference columns
that do not exist yet.

**Design change after review.** Tasks 1 through 3 originally appended the two
department columns to the existing `Form Items Extension` sheet and projected
them to one row per abbreviation with `distinct`. PR #4728 review rejected that
— the department a question rates is a property of the abbreviation alone, so
storing it at `(form_id, item_id)` grain forced Ops to enter the same value up
to four times and made contradictory entries representable. The mapping now
lives on its own sheet at its own grain, and the `distinct`, its
grain-projection CTE, and the guard test that propped it up are all gone.

## Global Constraints

- Target project is `kipptaf`. Every dbt command runs through `uv run`, never a
  bare `dbt`.
- Column names, verbatim: `abbreviation`, `rated_department_code`,
  `rated_department_name`. All three `string`.
- A sheet's declared `columns:` bind **positionally** after
  `skip_leading_rows: 1`. Never insert a column into the middle of a mapped tab;
  reference columns for the humans filling a sheet belong past the last mapped
  column, outside the named range.
- The crosswalk's `sheet_range` is the named range
  `src_google_forms__question_department_crosswalk`, spanning
  `'Question Department Crosswalk'!A:C`. A range that disagrees with the
  `columns:` list is a silent error, not a build failure.
- `abbreviation` is unique on the crosswalk, but only **after lowering** — the
  join lowers both sides, so uniqueness is asserted on `lower(abbreviation)`,
  not by a column-level `unique` test.
- `abbreviation` is nullable in practice: a row-unbounded named range can
  surface fully-blank phantom rows below the data, which is what makes the
  sibling `form_items_extension` sheet stage roughly 525 nulls out of 881 rows.
  Do not add `not_null` to it; filter `where abbreviation is not null` in every
  consumer.
- No `ORDER BY`, no `QUALIFY`, no subqueries against tables or CTEs, max one
  level of function nesting, trailing commas in every `SELECT`. See
  `src/dbt/CLAUDE.md` → SQL conventions.
- PII stays local. Respondent names and survey free text never appear in a
  commit, PR, issue, or comment.

---

### Task 1: Create the question-department crosswalk sheet

**Owner:** Ops / the user. No repo change. Nothing downstream works until this
lands, and the dbt tasks below fail their build until it does.

**Files:** none. Google Sheet `1OvJ95fuDCWVu9YQoVZnjauC8mdpgL4BmqdfqvgT7gAw`
(titled `Google Forms`), a new tab alongside `Form Items Extension`.

Steps 1 and 2 undo the original approach; Steps 3 through 6 build the crosswalk
at its own grain.

- [x] **Step 1: Delete the two columns from `Form Items Extension`**

Confirm `G1` reads `Rated Department Code` and `H1` reads
`Rated Department Name`, then delete columns G and H.

Both external tables — `kipptaf_google_sheets` and
`zz_stg_kipptaf_google_sheets` — only ever declared 6 columns, so the delete
needs no re-staging and breaks nothing.

- [x] **Step 2: Confirm the named range clamped back**

Data → Named ranges → `src_google_forms__form_items_extension` must read
`'Form Items Extension'!A:F`. Sheets normally clamps it when the columns are
deleted; if it still reads `A:H`, edit it.

- [x] **Step 3: Add the crosswalk tab**

Name it `Question Department Crosswalk`, in the same spreadsheet. Drive access
is already granted there, and multi-source spreadsheets are the norm — one
spreadsheet backs 10 sources elsewhere in `sources-external.yml`.

- [x] **Step 4: Seed it**

Header row `abbreviation`, `rated_department_code`, `rated_department_name` in
`A1:C1`, then one row per distinct lowered abbreviation from the form items
sheet — 309 of them:

```sql
select distinct lower(abbreviation) as abbreviation,
from
    `teamster-332318.kipptaf_google_sheets.src_google_sheets__google_forms__form_items_extension`
where abbreviation is not null
order by abbreviation
```

- [x] **Step 5: Create the named range**

`src_google_forms__question_department_crosswalk` over
`'Question Department Crosswalk'!A:C`. Reference columns past C are fine and are
ignored by BigQuery, but they must sit **outside** the range — the source binds
columns positionally.

- [x] **Step 6: Fill the codes**

Task 6's taxonomy. Verified against the staged table: 66 of 309 abbreviations
carry a code, all 14 agreed codes are used, each code maps to exactly one
display name, and the 243 blanks arrive as `NULL` rather than empty string, so
`accepted_values` passes on them.

---

### Task 2: Add the crosswalk source, staging model, and tests

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` — remove
  the two department columns from
  `src_google_sheets__google_forms__form_items_extension`, add the
  `src_google_sheets__google_forms__question_department_crosswalk` source block
  after it
- Revert:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__google_forms__question_department_crosswalk.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__question_department_crosswalk.yml`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__google_forms__question_department_crosswalk__unique_lowered_abbreviation.sql`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__google_forms__question_department_crosswalk__covers_all_abbreviations.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`
- Delete:
  `src/dbt/kipptaf/tests/stg_google_sheets__google_forms__form_items_extension__one_department_per_abbreviation.sql`

**Interfaces:**

- Consumes: the crosswalk tab from Task 1.
- Produces: `stg_google_sheets__google_forms__question_department_crosswalk`
  with `abbreviation`, `rated_department_code`, `rated_department_name`, all
  `string`, one row per lowered abbreviation.

The `form_items_extension` revert is mandatory, not cosmetic. Once Task 1
deletes columns G and H, a source block still declaring 8 columns fails the
staging contract, which enforces `name` plus `data_type` on every declared
column.

- [x] **Step 1: Swap the source blocks**

Drop `rated_department_code` and `rated_department_name` from the
`form_items_extension` `columns:` list, then add the new source after it. The
`sheet_range` is the named range from Task 1 Step 5, not the tab name:

```yaml
- name: src_google_sheets__google_forms__question_department_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/1OvJ95fuDCWVu9YQoVZnjauC8mdpgL4BmqdfqvgT7gAw
      sheet_range: src_google_forms__question_department_crosswalk
      skip_leading_rows: 1
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - sheets
          - google_forms
          - question_department_crosswalk
  columns:
    - name: abbreviation
      data_type: string
    - name: rated_department_code
      data_type: string
    - name: rated_department_name
      data_type: string
```

- [x] **Step 2: Add the staging model**

A bare `select *` over the source, matching every other sheet staging model. No
Dagster Python change is needed — the asset comes from the `asset_key` meta
above.

- [x] **Step 3: Declare the staging contract**

`accepted_values` on `rated_department_code` against the 14 agreed codes, at
`severity: error`. Nulls pass it without an entry: the test compiles to
`where value not in (...)`, which `NULL` never satisfies.

Do **not** add `not_null` to `abbreviation`. The named range is row-unbounded,
so BigQuery can surface fully-blank phantom rows below the data — that is what
makes the sibling `Form Items Extension` sheet stage roughly 525 null
abbreviations out of 881 rows. Every consumer filters
`where abbreviation is not null` instead.

- [x] **Step 4: Add the two singular tests**

`unique_lowered_abbreviation` (error) asserts one row per lowered abbreviation.
It replaces a column-level `unique` rather than joining it: the join in Task 3
lowers both sides, so `A1` and `a1` would both pass `unique` and then collide,
fanning out every response for that question. Uniqueness on the lowered value
subsumes uniqueness on the raw value.

`covers_all_abbreviations` (warn) asserts every non-null abbreviation in the
form items sheet has a crosswalk row. This is the one failure mode the redesign
introduces — a question on a new form arrives with no mapping. It fails safe,
because a null department routes to the most restricted audience, so it warns
rather than blocking a build.

- [x] **Step 5: Delete the old guard test**

`one_department_per_abbreviation` existed only to make the `distinct` in the old
join a projection rather than a dedupe. With the mapping stored at grain there
is nothing to project, so both the test file and its `tests/properties.yml`
entry go.

- [x] **Step 6: Parse**

```bash
uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf --target staging
```

A stale partial-parse manifest surfaces as
`'model...' depends on 'snapshot...' which is not in the graph!` on the next
`run-operation`. `--no-partial-parse` clears it.

---

### Task 3: Carry the mapping through `int_surveys__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`

**Interfaces:**

- Consumes: `stg_google_sheets__google_forms__question_department_crosswalk`
  from Task 2.
- Produces: the same two columns on `int_surveys__survey_responses`, one value
  per response row, null where the question is absent from the crosswalk.

- [x] **Step 1: Add the mapping CTE**

Insert after the `enriched` CTE's closing paren, before the final `select`.
There is no `distinct` and no grain projection — the crosswalk is already one
row per abbreviation. Plain columns come before the `lower()` expression,
because ST06 orders simple functions after column enumerations and sqlfluff
fails the reverse.

```sql
    question_departments as (
        /* the crosswalk is already one row per abbreviation, so this joins at
           grain with no projection. Lowered on both sides because sheet entry is
           not case-constrained; the crosswalk's unique_lowered_abbreviation test
           is what keeps lowering from collapsing two rows into a fan-out. */
        select
            rated_department_code,
            rated_department_name,

            lower(abbreviation) as question_shortname,
        from
            {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
        where abbreviation is not null
    )
```

The `where` clause guards the row-unbounded named range described in Task 2
Step 3. Phantom rows could not match the join on their own, since `NULL` equals
nothing, but they would collide with each other under
`unique_lowered_abbreviation` and fail it spuriously — so every consumer
filters.

- [x] **Step 2: Rewrite the final select**

The `lower()` sits in the join predicate. An earlier version materialized it as
a `question_shortname_key` column in an extra `enriched_keyed` CTE and then
dropped it again with `except`; that scaffolding bought nothing and is gone.
`question_shortname` keeps its original case in the output — consumers depend on
that.

```sql
select
    e.*,

    qd.rated_department_code,
    qd.rated_department_name,

    coalesce(
        cast(e.respondent_employee_number as string), e.respondent_email
    ) as respondent_identifier,
from enriched as e
left join
    question_departments as qd on lower(e.question_shortname) = qd.question_shortname
```

- [x] **Step 3: Declare both columns**

Add `rated_department_code` and `rated_department_name` to
`properties/int_surveys__survey_responses.yml` with descriptions naming the
crosswalk as the source.

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

**Files:** none.

- [x] **Step 1: Create the staging external**

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__google_forms__question_department_crosswalk" \
  --target staging --project-dir src/dbt/kipptaf
```

The selector is `<source_name>.<table_name>` — not project-qualified. No
`ext_full_refresh` is needed or wanted here: the table is new, and the macro
only skips tables that already exist. That also keeps the run outside the
authorization gate that a drop-and-recreate of a shared `zz_stg` table trips.

`form_items_extension` needs no re-staging — its external table always declared
6 columns, so Task 1's column delete brought the sheet back into agreement with
it.

- [x] **Step 2: Build**

```bash
uv run dbt build --target staging --project-dir src/dbt/kipptaf \
  --select stg_google_sheets__google_forms__question_department_crosswalk \
  stg_google_sheets__google_forms__question_department_crosswalk__unique_lowered_abbreviation \
  stg_google_sheets__google_forms__question_department_crosswalk__covers_all_abbreviations \
  int_surveys__survey_responses rpt_tableau__survey_responses
```

Verified: `PASS=11 WARN=1 ERROR=0`. The crosswalk staged at 309 rows, and
`accepted_values`, `unique_lowered_abbreviation`, and `covers_all_abbreviations`
all passed — coverage at 309 of 309.

The one warning is pre-existing and unrelated:
`dbt_utils_expression_is_true_int_surveys__survey_responses_...` reports 480
rows in prod as well as in staging. Tracked in #4974.

- [x] **Step 3: Confirm the join added no rows**

The decisive check is the model's own grain test, not a row count.
`dbt_utils_unique_combination_of_columns` on
`(survey_id, survey_response_id, survey_question_id, question_shortname, answer)`
**passed** — that is the exact test a fan-out breaks.

Row counts corroborate it. Staged `rpt_tableau__survey_responses` held 3,619,668
rows against prod's 3,619,735. Diffing the response keys found 1 row prod-only
and **0 rows staging-only**: a single survey response submitted after `zz_stg`
was cloned, times its 67 question rows. A left join cannot drop rows, and
nothing appears in staging that is absent from prod.

115,434 rows carry a department code, across 13 of the 14 codes.

---

### Task 6: Populate the department taxonomy and pin it with a test

**Owner:** Ops, with the data team. **Blocked on open question 1** in the spec:
merged departments must resolve to one code, and the SUP-side `cmo_*` /
`regional_*` scopes need a decision — one code per department, or separate codes
per scope.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__google_forms__question_department_crosswalk.yml`

- [x] **Step 1: Fill in the sheet**

For every abbreviation that rates a department, enter the agreed code in column
B and its label in column C of the crosswalk tab. Leave both blank on
`open_ended_*`, `*_overall_*`, `supplies`, `respondent_name`, `school_based`,
and every section header. Two abbreviations break their own naming scheme and
must be entered by hand rather than pattern-filled: `sre_oe` belongs with
`student_recruitment_*`, and `teaching_and_learning_oe` belongs with
`teaching_learning_*`.

One row per abbreviation means there is nothing to copy down and no way to enter
a contradictory pair — that is the point of the separate sheet. Verified on
completion: 66 of 309 abbreviations carry a code, all 14 codes are in use, and
each code maps to exactly one display name.

- [x] **Step 2: Pin the agreed list**

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

- [x] **Step 3: Verify nothing fanned out**

Re-run Task 5 Step 2 and Step 3. The functional-dependency test is now doing
real work — a code entered inconsistently across two rows sharing an
abbreviation fails it.

---

### Department taxonomy, as shipped

Open question 1 is resolved. One code per function, with `regional_*` and
`cmo_*` question families folded into the unprefixed function. Fourteen codes,
pinned by `accepted_values` on `rated_department_code`:

`compliance`, `data`, `development`, `finance`, `human_resources_operations`,
`leadership_development`, `marketing_comms_enrollment`, `operations`,
`real_estate_facilities`, `special_education`, `talent_acquisition`,
`teacher_development`, `teaching_learning`, `technology`

Three merges are not derivable from the question names and must be preserved on
any future sheet edit:

- `purchasing_*` carries `finance`.
- `student_recruitment_*` and `sre_oe` carry `marketing_comms_enrollment`.
- `real_estate_*` and `regional_facilities_*` both carry
  `real_estate_facilities`.

The retired `advocacy_*` questions carry `development`. Sixty-seven of the
sheet's 403 populated rows carry a code; the rest rate no department and stay
null, which the gate routes to its most restricted audience.

---

### Task 7: Tableau remediation slice

**Owner:** the user, in Tableau Desktop. Independent of Tasks 1 through 6 and
shippable before them. Every item narrows access or deletes dead code.
Authoritative calc text:
`docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md` (the guide
no longer carries calc text).

An audit of the workbook on 2026-08-05 found two of these steps already done and
two narrower than written. Struck items below are confirmed complete — do not
redo them.

**Files:** the Survey Dashboard workbook.

- [ ] **Step 1: Add small-cell suppression to `support_open_ended`** — narrowed

`Permissions - Support` is **already applied** to this sheet, so only the
suppression is missing. The other four support sheets carry an `Employee Number`
quantitative filter; this one does not. Add it to match.

- [ ] **Step 2: Scope the blanket KTAF grant**

In `Permissions - Support`, the branch granting unconditionally to
`KNJ-SG-Tableau All Staff KTAF` becomes region-scoped, matching the entity gate
in the permissions guide. Central office staff keep access to their own regions,
not to everything.

- [x] ~~**Step 3: Delete `Permissions - Support (Preview)`**~~ — **done**

Already gone. The 2026-08-05 audit enumerated every calculated field in the
workbook and found exactly two beginning `Permissions`: `Permissions - ITR` and
`Permissions - Support`.

- [x] ~~**Step 4: Remove `KNJ-SG-Tableau The Syndicate` from the support
      fields**~~ — **done**

`Permissions - Support` carries no Syndicate branch.

!!! danger "Do not extend this to `Permissions - ITR`"

    `Permissions - ITR` branch 3b grants to `KNJ-SG-Tableau The Syndicate`
    deliberately — it is one of the three regional viewer groups, each with its own
    peer exclusion. Removing it would silently drop the Syndicate's regional
    visibility of Intent to Return. The network-wide retirement of this group
    applies to the all-access tiers, not to a scoped, peer-excluded branch.

- [x] ~~**Step 5: Apply the #4656 renames**~~ — **done**

Resolved by refreshing the workbook's datasources rather than by renaming
fields.

`rpt_tableau__survey_responses` already carried the post-#4656 names. The
`rpt_tableau__survey_completion` extract did not — at audit time it still held
`business_unit`, `department` and `location`, and no identity columns at all —
but every gated workbook has since been refreshed onto the current datasources,
so the pre-#4656 names are gone and the Tier 1 identity columns are present.

!!! warning "Re-read the captions on any calc you carry across"

    A refresh brings new columns in unnamed and can leave an old caption on a
    different column, so a caption list from before the refresh is not reliable.
    Resolve by underlying column — see step 1 of
    `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`, which has a
    live example of one caption meaning two different things in one workbook.

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
