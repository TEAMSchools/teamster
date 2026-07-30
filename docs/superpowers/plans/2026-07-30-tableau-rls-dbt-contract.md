# Tableau RLS dbt Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every dbt model backing a permission-gated Tableau workbook exposes
the same identity, location, and entity columns under the same names, so one
Permissions block works across all 13 workbooks unmodified.

**Architecture:** Each extract joins `int_people__location_crosswalk` on its raw
`home_work_location_name` and selects a fixed list of eleven columns under their
**real source names** — no aliasing, no macro. Uniformity comes from every model
selecting the same source columns. One new extract replaces a workbook's direct
dependency on an intermediate model.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, sqlfluff via Trunk.

## Global Constraints

- Design doc:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`.
- Checkout: `/workspaces/teamster`, already on branch
  `cristinabaldor/feat/claude-tableau-rls-entra-migration`. No worktree — do not
  create one, do not switch branches, do not push except in the final task.
- `uv run dbt deps` must be run once per session before any dbt command. Without
  it every command fails with "dbt found 2 package(s) specified in packages.yml,
  but only 0 package(s) installed".
- Always `uv run dbt`, never a bare `dbt`.
- **No macros and no aliasing for the contract columns.** Column lists live
  inline in each model, under the real source column names. A previous revision
  used a macro; it was reverted deliberately in commit `284110120`. Do not
  reintroduce one, and do not rename a source column to something tidier.
- Location values come from
  `int_people__location_crosswalk.location_clean_name`, **never** the raw
  `home_work_location_name`.
- Entity comes from `home_business_unit_name`, **never** `location_region`,
  which is a property of the location rather than the person.
- Contract columns describe the person whose access is being decided. Everyone
  else on the row keeps a descriptive prefix (`respondent_*`, `observer_*`).
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, trailing commas,
  single quotes, max line length 88.
- New columns need entries in the model's properties YAML.
- Do not modify `rpt_appsheet__stipend_app_roster`, `rpt_tableau__survey_links`,
  or any other shared upstream. The contract applies to leaf `rpt_tableau__*`
  extracts only.
- Renaming a column breaks every Tableau reference to it. That is expected and
  accepted; the affected workbooks are listed in the appendix. Do not add
  backwards-compatible aliases to avoid it.
- **Delete every legacy alias of a contract column.** User ruling, 2026-07-30: a
  model must emit exactly one name per value. If the model aliases a contract
  source column to anything else — `entity`, `` `location` ``, `legal_entity`,
  `region`, `department`, `report_to_sam_account_name` (singular),
  `respondent_location`, `teacher_location` — delete that alias and its YAML
  entry. Keep only columns that are genuinely a _different_ value for a
  _different_ person, which retain a descriptive prefix: `entity_short`,
  `observer_location`, and the `respondent_*` fields on
  `rpt_tableau__grants_timesheets`.

### The contract column list

Eleven columns, real source names, in this order. `ROSTER` is the model's staff
roster alias; `lc` is the location crosswalk alias.

```sql
    lc.location_clean_name,
    lc.campus_name,

    ROSTER.home_business_unit_name,
    ROSTER.home_department_name,
    ROSTER.job_function,
    ROSTER.job_title,

    ROSTER.mail,
    ROSTER.user_principal_name,
    ROSTER.sam_account_name,

    ROSTER.reports_to_mail,
    ROSTER.reports_to_sam_account_name,
```

All eleven source columns are confirmed present on `int_people__staff_roster`,
`int_people__staff_roster_history`, and `int_people__location_crosswalk`
(verified against BigQuery INFORMATION_SCHEMA on 2026-07-30). A "column not
found" error means a join or alias mistake, not a missing source column.

### The crosswalk join

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on ROSTER.home_work_location_name = lc.location_name
```

### Standard Checks

Every model task ends with these four steps. `MODEL` is the model name; `FILES`
are the `.sql` and `.yml` paths.

```bash
# 1. Build
uv run dbt build --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select MODEL --target dev

# 2. Prove the contract columns resolve and location is a clean name
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select distinct location_clean_name, home_business_unit_name from {{ ref('MODEL') }} order by 2, 1" \
  --limit 50 --target dev

# 3. Lint
cd /workspaces/teamster && /workspaces/teamster/.trunk/tools/trunk check \
  --force --no-fix FILES </dev/null

# 4. Commit
git add FILES && git commit -m "feat(dbt): apply tableau access contract to MODEL

Refs #4638"
```

Step 2 must return clean names such as `KIPP Hatch Middle` and
`KIPP Sumner Elementary`. Seeing `KIPP Hatch Academy` or `KIPP Sumner Academy`
means the raw `home_work_location_name` is still being selected.

### Duplicate-column trap

The contract selects all eleven columns bare. If the model's select list already
produces any same-named column, BigQuery fails the build with a
duplicate-output-column error at `CREATE VIEW`.

**Check by name equality against the model's actual select list — do not rely on
this plan's delete-list being exhaustive.** Task 1 hit exactly this: the model
already had an unaliased `srh.sam_account_name,` that the plan did not name.
Read the whole select list, compare every output name against the eleven, and
delete the pre-existing duplicates.

### Contract enforcement makes YAML mandatory

`extracts/` inherits `contract: enforced: true` (see
`src/dbt/kipptaf/CLAUDE.md`). Every output column must have a properties YAML
entry or the build fails. So:

- Each of the eleven needs a YAML entry unless an identically-named entry
  already exists. A differently-named legacy entry does not count —
  `report_to_sam_account_name` (singular) does not satisfy
  `reports_to_sam_account_name` (plural).
- Per `src/dbt/CLAUDE.md`, columns carrying data tests sort to the top of the
  `columns:` list.

---

### Task 1: `rpt_tableau__content_team` — reference implementation

Eleven more models follow this exact shape. Get it right here.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__content_team.sql` (49
  lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__content_team.yml`

**Interfaces:**

- Consumes: `int_people__location_crosswalk`.
- Produces: the eleven contract columns on `rpt_tableau__content_team`. Read
  directly by the Content Team Dashboard and Miami Instructional Rubrics
  workbooks. No dbt model consumes it.

- [ ] **Step 1: Add the crosswalk join**

The roster alias is `srh` (`int_people__staff_roster_history`). Add after the
existing roster join:

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete the old aliases and add the contract columns**

Delete `srh.home_business_unit_name as entity,` (line 24) and
``srh.home_work_location_name as `location`,`` (line 25), plus any existing
`job_title` or department column in the same select list. Then add:

```sql
    lc.location_clean_name,
    lc.campus_name,

    srh.home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,
```

- [ ] **Step 3: Document the new columns in the properties YAML**

Nest these under the existing `columns:` key, matching that file's current
indentation:

```yaml
- name: location_clean_name
  data_type: string
  description: >-
    Canonical location from int_people__location_crosswalk. Drives the Tableau
    location gate; retired name aliases collapse onto their canonical clean name
    here.
  data_tests:
    - not_null
- name: home_business_unit_name
  data_type: string
  description: >-
    Legal entity. Drives the Tableau entity gate. Never location_region, which
    is a property of the location rather than the person.
  data_tests:
    - not_null
    - accepted_values:
        arguments:
          values:
            - TEAM Academy Charter School
            - KIPP Cooper Norcross Academy
            - KIPP Miami
            - KIPP Paterson
            - KIPP TEAM and Family Schools Inc.
- name: campus_name
  data_type: string
- name: home_department_name
  data_type: string
- name: job_function
  data_type: string
  description: Drives the AP role predicate; NULL for 63 active staff.
- name: mail
  data_type: string
  description: Post-cutover Tableau identity.
- name: user_principal_name
  data_type: string
- name: reports_to_mail
  data_type: string
- name: reports_to_sam_account_name
  data_type: string
- name: job_title
  data_type: string
- name: sam_account_name
  data_type: string
```

Add an entry only where one does not already exist under that exact name.
`job_title` and `sam_account_name` are often already documented; a legacy
`report_to_sam_account_name` (singular) does not satisfy the plural.

- [ ] **Step 4: Run the Standard Checks**

`MODEL` is `rpt_tableau__content_team`; `FILES` are the two paths above.

---

### Task 2: `rpt_tableau__leadership_development`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__leadership_development.sql`
  (162 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__leadership_development.yml`

**Interfaces:** consumes `int_people__location_crosswalk`; produces the eleven
contract columns. Read by the Leadership Development workbook.

- [ ] **Step 1: Add the crosswalk join.** Roster alias is `r`.

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on r.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete `r.home_business_unit_name as entity,` (L121) and
      ``r.home_work_location_name as `location`,`` (L122), plus any pre-existing
      output column whose name matches one of the eleven. Then add:**

```sql
    lc.location_clean_name,
    lc.campus_name,

    r.home_business_unit_name,
    r.home_department_name,
    r.job_function,
    r.job_title,

    r.mail,
    r.user_principal_name,
    r.sam_account_name,

    r.reports_to_mail,
    r.reports_to_sam_account_name,
```

- [ ] **Step 3: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.
- [ ] **Step 4: Run the Standard Checks.** `MODEL` is
      `rpt_tableau__leadership_development`.

---

### Task 3: `rpt_tableau__schoolmint_grow_goals`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__schoolmint_grow_goals.sql`
  (72 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__schoolmint_grow_goals.yml`

**Interfaces:** consumes `int_people__location_crosswalk`; produces the eleven
contract columns. Read by the SchoolMint Grow Dashboard.

- [ ] **Step 1: Add the crosswalk join.** Roster alias is `srh`.

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete `srh.home_business_unit_name as entity,` (L4) and
      ``srh.home_work_location_name as `location`,`` (L5), plus any pre-existing
      output column whose name matches one of the eleven. Then add:**

```sql
    lc.location_clean_name,
    lc.campus_name,

    srh.home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,
```

- [ ] **Step 3: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.
- [ ] **Step 4: Run the Standard Checks.** `MODEL` is
      `rpt_tableau__schoolmint_grow_goals`.

---

### Task 4: `rpt_tableau__schoolmint_grow_observation_details` — two select blocks

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__schoolmint_grow_observation_details.sql`
  (283 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__schoolmint_grow_observation_details.yml`

**Interfaces:** consumes `int_people__location_crosswalk`; produces the eleven
contract columns. Read by the SchoolMint Grow Dashboard and the Coaching
Conversation Tool.

This model has **two** select blocks that both emit `entity` and
`` `location` `` — at L29-30 and L185-186. Both need the contract columns, and
the crosswalk join must be in scope for both.

- [ ] **Step 1: Add the crosswalk join in both blocks' scope.** Roster alias is
      `srh`.

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: In both blocks, delete the `entity` and `` `location` `` aliases
      plus any pre-existing output column matching one of the eleven, and add:**

```sql
    lc.location_clean_name,
    lc.campus_name,

    srh.home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,
```

- [ ] **Step 3: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.

- [ ] **Step 4: Confirm neither block was missed**

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select count(*) as rows_missing_location from {{ ref('rpt_tableau__schoolmint_grow_observation_details') }} where location_clean_name is null" \
  --target dev
```

A count materially higher than the row count of one block means a block was
missed. Report the number either way — some nulls are expected where the roster
join misses staff on Leave.

- [ ] **Step 5: Run the Standard Checks.**

---

### Task 5: `rpt_tableau__teacher_observations` — two select blocks

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__teacher_observations.sql`
  (191 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__teacher_observations.yml`

**Interfaces:** consumes `int_people__location_crosswalk`; produces the eleven
contract columns. Read by the SchoolMint Grow Dashboard.

Two select blocks emit `entity` and `` `location` `` — at L69-70 and L134-135.

- [ ] **Step 1: Add the crosswalk join in both blocks' scope.** Roster alias is
      `rh`.

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on rh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: In both blocks, delete the `entity` and `` `location` `` aliases
      plus any pre-existing output column matching one of the eleven, and add:**

```sql
    lc.location_clean_name,
    lc.campus_name,

    rh.home_business_unit_name,
    rh.home_department_name,
    rh.job_function,
    rh.job_title,

    rh.mail,
    rh.user_principal_name,
    rh.sam_account_name,

    rh.reports_to_mail,
    rh.reports_to_sam_account_name,
```

- [ ] **Step 3: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.
- [ ] **Step 4: Confirm neither block was missed** using Task 4 Step 4's query
      with this model name.
- [ ] **Step 5: Run the Standard Checks.**

---

### Task 6: `rpt_tableau__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_responses.sql`
  (55 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_responses.yml`

**Interfaces:** consumes `int_people__location_crosswalk`; produces the eleven
contract columns. Read by the Survey Dashboard. `rpt_tableau__survey_completion`
(Task 9) selects `employee_number`, `academic_year`, `survey_code`,
`survey_response_id`, and `date_submitted` from this model — none of which this
task touches, so the downstream model is unaffected.

Note this model's entity alias is `legal_entity`, not `entity`.

- [ ] **Step 1: Add the crosswalk join.** Roster alias is `eh`.

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on eh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete `eh.home_business_unit_name as legal_entity,` (L21) and
      ``eh.home_work_location_name as `location`,`` (L24), plus any pre-existing
      output column matching one of the eleven. Then add:**

```sql
    lc.location_clean_name,
    lc.campus_name,

    eh.home_business_unit_name,
    eh.home_department_name,
    eh.job_function,
    eh.job_title,

    eh.mail,
    eh.user_principal_name,
    eh.sam_account_name,

    eh.reports_to_mail,
    eh.reports_to_sam_account_name,
```

This model already emits `mail` — if it does so from the same roster alias,
delete the old line rather than adding a duplicate.

- [ ] **Step 3: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.
- [ ] **Step 4: Run the Standard Checks.** `MODEL` is
      `rpt_tableau__survey_responses`.

---

### Task 7: `rpt_tableau__operations_ekg`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__operations_ekg.sql` (73
  lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__operations_ekg.yml`

**Interfaces:** consumes `int_people__location_crosswalk` (already referenced);
produces the eleven contract columns. Read by the Operations Systems workbook.

This model already references the crosswalk and emits
`home_work_location_name as respondent_location` (L7) and a `region` column.

- [ ] **Step 1: Read the whole model first.** Identify the roster alias, the
      existing crosswalk alias, and whether `respondent_location` describes the
      person whose access is being decided.

  - If it describes the gated person, replace it with `location_clean_name`.
  - If it describes someone else, keep it under its prefix and add the contract
    columns alongside.

  State which you concluded, and why, in your report.

- [ ] **Step 2: Reuse the existing crosswalk join** — do not add a second one.

- [ ] **Step 3: Delete `region`** (it derives from `location_region`, which is
      the location's region rather than the person's entity) **and add the
      eleven contract columns** using the model's actual roster alias.

- [ ] **Step 4: Add the YAML entries** from Task 1 Step 3, only for names not
      already present.
- [ ] **Step 5: Run the Standard Checks.** `MODEL` is
      `rpt_tableau__operations_ekg`.

---

### Task 8: `rpt_tableau__operations_pm`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__operations_pm.sql` (117
  lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__operations_pm.yml`

**Interfaces:**

- Consumes: `int_people__location_crosswalk` (already referenced),
  `int_people__staff_roster`.
- Produces: the eleven contract columns. Read by the Operations Systems
  workbook.

This model already joins the crosswalk via a `schools` CTE at L106
(`on ops_pm_roster.home_work_location_name = schools.location_name`) and emits
`schools.location_region as region` at L91.

- [ ] **Step 1: Reuse the existing crosswalk join**

Do not add a second join. Read L60-117 to find which alias exposes
`location_clean_name`, and select from that.

- [ ] **Step 2: Delete `region` and add the contract columns**

`region` is derived from `location_region` and must not survive — it is the
location's region, not the person's entity. Replace it with
`home_business_unit_name` from the roster alias `ops_pm_roster`.

- [ ] **Step 3: Document, then run the Standard Checks**

`MODEL` is `rpt_tableau__operations_pm`.

---

### Task 9: `rpt_tableau__survey_completion`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_completion.sql`
  (48 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_completion.yml`

**Interfaces:**

- Consumes: `int_people__staff_roster`, `int_people__location_crosswalk`.
- Produces: the eleven contract columns. Read by the Survey Dashboard and
  Personalized Survey Links workbooks.

This model has no roster join. It selects `sl.location`, `sl.business_unit`,
`sl.department`, `sl.job_title`, and `sl.mail` from `rpt_tableau__survey_links`,
which is **out of scope**. Add a roster join here instead.

- [ ] **Step 1: Add roster and crosswalk joins**

```sql
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on sl.employee_number = sr2.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr2.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete the inherited columns and add the contract columns**

Delete `sl.business_unit,`, `sl.location,`, `sl.department,`, `sl.job_title,`,
and `sl.mail,`. Add the contract block with `sr2` as the roster alias.

- [ ] **Step 3: Confirm the join did not fan out**

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select count(*) as ct, count(distinct format('%T|%T|%T', employee_number, academic_year, survey_round)) as distinct_key from {{ ref('rpt_tableau__survey_completion') }}" \
  --target dev
```

Expected: `ct` equals `distinct_key`. If `ct` is larger,
`int_people__staff_roster` returned more than one row per `employee_number` and
the join needs an `is_current` predicate.

- [ ] **Step 4: Document, then run the Standard Checks**

---

### Task 10: `rpt_tableau__stipend_and_bonus_app`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__stipend_and_bonus_app.sql`
  (35 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__stipend_and_bonus_app.yml`

**Interfaces:**

- Consumes: `int_people__staff_roster`, `int_people__location_crosswalk`.
- Produces: the eleven contract columns. Read by the Stipend and Bonus
  Dashboard.

Location and entity currently come from `rpt_appsheet__stipend_app_roster` as
`r.location` and `r.entity`. That roster is out of scope. `r1` and `r2` already
alias `int_people__staff_roster` for the two approvers — use `r3` for the
subject to avoid collision.

- [ ] **Step 1: Add roster and crosswalk joins**

```sql
left join
    {{ ref("int_people__staff_roster") }} as r3
    on o.employee_number = r3.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on r3.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Delete the passthrough columns and add the contract columns**

Delete `r.job_title,`, `r.department,`, `r.location,`, and `r.entity,`. Add the
contract block with `r3` as the roster alias. Keep `r.entity_short`,
`r.position_id`, `r.formatted_name as teammate`, and
`r.payroll_group_code as company_code` — not contract columns.

- [ ] **Step 3: Confirm no fan-out using `event_id` as the distinct key, then
      run the Standard Checks**

---

### Task 11: `rpt_tableau__grants_timesheets`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__grants_timesheets.sql`
  (53 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__grants_timesheets.yml`

**Interfaces:**

- Consumes: `int_people__staff_roster`, `int_people__location_crosswalk`.
- Produces: the eleven contract columns describing the **respondent** — the
  person certifying their own time. Read by the Federal Grants Timesheet
  Approval workbook.

No roster join and no `mail` today; columns come from an Alchemer source with
`respondent_*` prefixes. Keep the existing `respondent_*` columns.

- [ ] **Step 1: Add roster and crosswalk joins inside the `sub` CTE**

```sql
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on ri.respondent_employee_number = sr2.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr2.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Add the contract columns to the `sub` CTE**

Use `sr2` as the roster alias.

- [ ] **Step 3: Pass all eleven through the outer select**

The outer select enumerates columns explicitly and feeds a `pivot`, so any
column not listed is dropped silently. Add after `respondent_primary_job`:

```sql
    location_clean_name,
    campus_name,
    home_business_unit_name,
    home_department_name,
    job_function,
    job_title,
    mail,
    user_principal_name,
    sam_account_name,
    reports_to_mail,
    reports_to_sam_account_name,
```

- [ ] **Step 4: Verify the columns survived the pivot**

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select location_clean_name, home_business_unit_name, mail from {{ ref('rpt_tableau__grants_timesheets') }} limit 5" \
  --target dev
```

A "column not found" error means Step 3 was skipped or the pivot dropped them.

- [ ] **Step 5: Document, then run the Standard Checks**

---

### Task 12: `rpt_tableau__pm_outlier_detection` — two location axes

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__pm_outlier_detection.sql`
  (167 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__pm_outlier_detection.yml`

**Interfaces:**

- Consumes: `int_people__location_crosswalk`.
- Produces: the eleven contract columns describing **the observed teacher**,
  plus the existing `observer_location` retained unchanged. Read by the
  SchoolMint Grow Dashboard.

This model carries both an observer and an observed teacher. Access gates on the
**teacher**. The teacher roster alias is `sa` (L146); the observer alias is
`srh` (L139).

- [ ] **Step 1: Add the crosswalk join keyed on the teacher**

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sa.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Replace `teacher_location` with the contract columns**

Delete `sa.home_work_location_name as teacher_location,` (L146) and add the
contract block with `sa` as the roster alias. Leave
`srh.home_work_location_name as observer_location,` (L139) **unchanged** — it
describes someone other than the gated person, so it keeps its prefix.

- [ ] **Step 3: Confirm both axes exist**

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select observer_location, location_clean_name from {{ ref('rpt_tableau__pm_outlier_detection') }} limit 5" \
  --target dev
```

Expected: both present and populated.

- [ ] **Step 4: Document, then run the Standard Checks**

In the YAML, state that `location_clean_name` describes the observed teacher and
gates access, while `observer_location` is descriptive only.

---

### Task 13: New extract `rpt_tableau__manager_survey_details`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__manager_survey_details.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__manager_survey_details.yml`
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`

**Interfaces:**

- Consumes: `int_surveys__manager_survey_details`, `int_people__staff_roster`,
  `int_people__location_crosswalk`.
- Produces: `rpt_tableau__manager_survey_details` with the eleven contract
  columns describing the **subject** (the person being rated), plus every
  existing column from the intermediate model.

Manager Survey Reports and Manager Survey Rollup read
`int_surveys__manager_survey_details` directly today. That model carries
`subject_samaccountname`, `subject_userprincipalname`, `subject_primary_site`,
and `subject_legal_entity_name`, but no `mail`.

- [ ] **Step 1: Create the model**

```sql
select
    msd.*,

    lc.location_clean_name,
    lc.campus_name,

    sr.home_business_unit_name,
    sr.home_department_name,
    sr.job_function,
    sr.job_title,

    sr.mail,
    sr.user_principal_name,
    sr.sam_account_name,

    sr.reports_to_mail,
    sr.reports_to_sam_account_name,
from {{ ref("int_surveys__manager_survey_details") }} as msd
left join
    {{ ref("int_people__staff_roster") }} as sr
    on msd.subject_df_employee_number = sr.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
```

Confirm the subject employee-number column name against the intermediate model
before running. If it differs from `subject_df_employee_number`, use the actual
name — do not add a rename.

`msd.*` may already expose a `job_title` or department column, which would
collide with the contract columns. If the build reports a duplicate, enumerate
`msd`'s columns explicitly instead of using `*`, omitting the colliding ones.

- [ ] **Step 2: Build and confirm no fan-out**

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select (select count(*) from {{ ref('int_surveys__manager_survey_details') }}) as int_ct, (select count(*) from {{ ref('rpt_tableau__manager_survey_details') }}) as rpt_ct" \
  --target dev
```

Expected: `int_ct` equals `rpt_ct`.

- [ ] **Step 3: Add the properties YAML**

Model description: this extract exists so the manager survey workbooks depend on
an `rpt_` model rather than an intermediate one, and the contract columns
describe the survey **subject**, not the respondent. Column entries as Task 1
Step 3.

- [ ] **Step 4: Update the exposures**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, repoint
`manager_survey_reports` from `ref("int_surveys__manager_survey_details")` to
`ref("rpt_tableau__manager_survey_details")`, and add three exposures following
the file's existing structure exactly:

- `manager_survey_rollup` → `ref("rpt_tableau__manager_survey_details")`
- `content_team_dashboard` → `ref("rpt_tableau__content_team")`
- `teacher_goals` → the model confirmed in Task 15

- [ ] **Step 5: Run the Standard Checks, including `exposures/tableau.yml` in
      the commit**

---

### Task 14: Cross-model invariant tests

**Files:**

- Create:
  `src/dbt/kipptaf/tests/assert_roster_locations_resolve_to_crosswalk.sql`
- Create: `src/dbt/kipptaf/tests/assert_tableau_location_set_expected.sql`
- Create: `src/dbt/kipptaf/tests/assert_staff_mail_populated_with_sam.sql`

**Interfaces:**

- Consumes: `int_people__staff_roster`, `int_people__location_crosswalk`.
- Produces: three singular tests. No model consumes these.

These catch the failure mode the rebuild exists to eliminate: a new or renamed
location silently resolving to no Tableau group.

- [ ] **Step 1: Coverage test**

```sql
-- Every active staff location must resolve to a canonical crosswalk name.
-- A new school added to ADP but not the locations sheet lands here.
select
    sr.home_work_location_name,
    count(*) as staff_ct,
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
where
    sr.assignment_status != 'Terminated'
    and sr.home_work_location_name is not null
    and lc.location_clean_name is null
group by 1
```

- [ ] **Step 2: Expected-value-set test**

```sql
-- The gated location values are a known set of 30. An addition should fail
-- loudly here rather than silently gate to nothing in Tableau.
with
    expected as (
        select distinct lc.location_clean_name,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.location_name
        where sr.assignment_status != 'Terminated'
    )

select count(*) as location_ct,
from expected
having count(*) != 30
```

- [ ] **Step 3: Identity-coverage test, warn-level**

One active record legitimately has neither value today, so an error-level test
would block every future run.

```sql
{{ config(severity="warn") }}

-- Anyone with a sam_account_name must also have a mail value, or they lose
-- self-access at cutover when USERNAME() starts returning email.
select
    sr.employee_number,
from {{ ref("int_people__staff_roster") }} as sr
where
    sr.assignment_status != 'Terminated'
    and sr.sam_account_name is not null
    and sr.mail is null
```

- [ ] **Step 4: Run all three**

```bash
uv run dbt test --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select assert_roster_locations_resolve_to_crosswalk \
    assert_tableau_location_set_expected \
    assert_staff_mail_populated_with_sam --target dev
```

Expected: the first two PASS with 0 rows; the third WARNs with 0 or 1 rows. All
three were verified against production data on 2026-07-30. A count above 1 on
the third means new records lost their mail value.

- [ ] **Step 5: Lint and commit**

---

### Task 15: Confirm the two unknown datasources

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` if Task 13 Step 4 left
  `teacher_goals` unresolved.

**Interfaces:**

- Produces: a confirmed model name for the `teacher_goals` exposure.

Teacher Goals and Manager Survey Rollup have no exposure, so their backing
models were inferred. Guessing puts a wrong dependency in the DAG.

- [ ] **Step 1: Read the workbook datasources from Tableau**

Use the Tableau MCP: `list-workbooks` filtered `name:eq:Teacher Goals`, then
`get-view` on its `defaultViewId` for upstream datasources. Repeat for
`Manager Survey Rollup`.

- [ ] **Step 2: Map each datasource to its dbt model**

Match against `models/exposures/tableau.yml`. If it maps to a model already
covered by Tasks 1-13, only the exposure is needed.

- [ ] **Step 3: If it maps to an uncovered model, stop and report**

An uncovered model means the contract has a gap and the plan needs a new task.
Report the model name rather than improvising.

- [ ] **Step 4: Add the exposure, lint, commit**

---

### Task 16: Full-selection build and push

**Interfaces:** consumes every prior task; produces a pushed branch.

- [ ] **Step 1: Build every touched model together**

```bash
uv run dbt build --project-dir /workspaces/teamster/src/dbt/kipptaf --target dev \
  --select rpt_tableau__content_team rpt_tableau__leadership_development \
    rpt_tableau__schoolmint_grow_goals rpt_tableau__schoolmint_grow_observation_details \
    rpt_tableau__teacher_observations rpt_tableau__survey_responses \
    rpt_tableau__survey_completion rpt_tableau__operations_ekg rpt_tableau__operations_pm \
    rpt_tableau__stipend_and_bonus_app rpt_tableau__grants_timesheets \
    rpt_tableau__pm_outlier_detection rpt_tableau__manager_survey_details
```

Expected: all models and tests PASS.

- [ ] **Step 2: Confirm every model exposes the contract columns**

For each of the 13:

```bash
uv run dbt show --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select location_clean_name, home_business_unit_name, mail, job_function from {{ ref('MODEL') }} limit 1" \
  --target dev
```

Expected: no "column not found" errors. This proves the contract holds and is
the precondition for any Tableau edit.

- [ ] **Step 3: Lint every changed file**

```bash
cd /workspaces/teamster && \
files=$(git diff --name-only origin/main...HEAD | grep -E '\.(sql|yml)$' | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix $files </dev/null
```

Filter to existing paths — a `--force` check over a deleted path hard-errors.

- [ ] **Step 4: Push and report**

```bash
git push -u origin cristinabaldor/feat/claude-tableau-rls-entra-migration
```

Report the branch name and stop. Do **not** open the PR — the Tableau half is
not done, and a PR implies the workbooks are ready.

---

### Task 17: Remove retained legacy aliases

Tasks 1-3 diverged on legacy aliases: Tasks 1 and 2 **kept**
`report_to_sam_account_name` (singular) alongside the new plural, while Task 3
**deleted** `home_department_name as department`. Both cannot be right — a model
emitting two names for the same value defeats the uniformity this plan exists to
create.

**Ruling: delete every legacy alias of a contract column.** The user's directive
is explicit — real source column names, uniform across models, and they will fix
the broken calcs. A retained alias is a second name for the same value and a
future source of drift.

**Files:** every model touched by Tasks 1-12, plus their properties YAML.

- [ ] **Step 1: Find every retained legacy alias**

```bash
cd /workspaces/teamster && rg -n \
  'as (entity|`location`|legal_entity|region|department|report_to_sam_account_name|report_to_email|email|location_name)\b' \
  src/dbt/kipptaf/models/extracts/tableau/
```

- [ ] **Step 2: Delete each one** from both the `.sql` select list and the
      properties YAML. Do not delete a column that is not a legacy name for one
      of the eleven contract columns — `entity_short`, `observer_location`, and
      `respondent_*` columns stay.

- [ ] **Step 3: Build every affected model and confirm each passes contract
      enforcement**

```bash
uv run dbt build --project-dir /workspaces/teamster/src/dbt/kipptaf --target dev \
  --select rpt_tableau__content_team rpt_tableau__leadership_development \
    rpt_tableau__schoolmint_grow_goals
```

- [ ] **Step 4: Lint and commit.** One commit; note in the message which aliases
      were removed from which models, so the Tableau side can be updated from
      the log.

---

## Appendix: Tableau workbooks broken by these renames

Dropping the aliases changes column names, which breaks every Tableau reference
to them. This is accepted; the workbook owner fixes the calcs. Minimum blast
radius per workbook:

| Current field                           | Becomes                                          | Workbooks to fix                                                                                                                                                |
| --------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[entity]`                              | `home_business_unit_name`                        | Coaching Conversation Tool, Leadership Development, SchoolMint Grow Dashboard, Stipend and Bonus Dashboard, Content Team Dashboard, Miami Instructional Rubrics |
| `[location]`                            | `location_clean_name`                            | Coaching Conversation Tool, SchoolMint Grow Dashboard, Stipend and Bonus Dashboard, Content Team Dashboard, Miami Instructional Rubrics                         |
| `[report_to_sam_account_name]`          | `reports_to_sam_account_name`                    | Coaching Conversation Tool, Leadership Development, SchoolMint Grow Dashboard                                                                                   |
| `[department]`                          | `home_department_name`                           | Leadership Development, SchoolMint Grow Dashboard                                                                                                               |
| `[legal_entity]`                        | `home_business_unit_name`                        | Survey Dashboard                                                                                                                                                |
| `[region]`, `[home_work_location_name]` | `home_business_unit_name`, `location_clean_name` | Operations Systems                                                                                                                                              |
| `[samaccountname]`, `[username]`        | `sam_account_name`, `mail`                       | Personalized Survey Links                                                                                                                                       |
| `[teacher_location]`                    | `location_clean_name`                            | SchoolMint Grow Dashboard                                                                                                                                       |
| `subject_*` prefixes                    | real names, via datasource repoint               | Manager Survey Reports, Manager Survey Rollup                                                                                                                   |

`job_title` and `sam_account_name` are already real source names and do not
move. Teacher Goals and Federal Grants Timesheet Approval have no rename impact.

This table covers references found in the audited Permissions calcs. A renamed
column breaks any other reference too — filters, tooltips, other sheets — so
treat it as the minimum per workbook.

## Out of scope

The Tableau remediation — the canonical Permissions block, the per-workbook
helper field, the 13 workbook edits, the Preview as User persona matrix, and the
`entra-ready` tagging — is a separate plan, executed by a human in Tableau
Desktop, and depends on this one being merged and built first.

Also excluded per the design doc: renaming canonical clean names upstream,
populating `job_function` for the 25 unclassified teachers, and the People
Operations data fixes.
