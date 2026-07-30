# Tableau RLS dbt Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every dbt model backing a permission-gated Tableau workbook emits the
same identity, location, and entity columns under the same names, so one
Permissions block works across all 13 workbooks unmodified.

**Architecture:** A single macro emits the standard column list from a staff
roster alias and a location crosswalk alias. Each extract joins
`int_people__location_crosswalk` on its raw `home_work_location_name`, calls the
macro, and drops the ad-hoc aliases it emitted before. One new extract replaces
a workbook's direct dependency on an intermediate model.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, sqlfluff via Trunk.

## Global Constraints

- Design doc:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`.
  Read it before Task 1.
- Checkout: `/workspaces/teamster`, already on branch
  `cristinabaldor/feat/claude-tableau-rls-entra-migration`. There is no worktree
  — do not create one, and do not switch branches.
- Setup, once per session before any dbt command:
  `uv run dbt deps --project-dir /workspaces/teamster/src/dbt/kipptaf`. Without
  it, every dbt command fails with "dbt found 2 package(s) specified in
  packages.yml, but only 0 package(s) installed". Verified 2026-07-30.
- Always `uv run dbt`, never a bare `dbt`.
- Location values come from
  `int_people__location_crosswalk.location_clean_name`, **never** the raw
  `home_work_location_name`. Values pass through unchanged — no renaming, no
  override mapping in dbt.
- Entity comes from the roster's `home_business_unit_name`, **never**
  `location_region`.
- Contract columns describe the person whose access is being decided. Everyone
  else on the row keeps a descriptive prefix.
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, trailing commas,
  single quotes, max line length 88.
- Every model needs a properties YAML entry for new columns.
- Do not modify `rpt_appsheet__stipend_app_roster` or other shared upstreams;
  the contract applies to leaf `rpt_tableau__*` extracts only.

---

### Task 1: The contract macro

**Files:**

- Create: `src/dbt/kipptaf/macros/tableau_access_columns.sql`
- Test: `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__content_team.sql`
  (smallest consumer, used as the macro's first real caller in Task 2)

**Interfaces:**

- Consumes: nothing.
- Produces: `tableau_access_columns(roster_alias, crosswalk_alias)` — a Jinja
  macro emitting exactly these eleven columns, in this order, each with a
  trailing comma: `location_name`, `campus_name`, `entity`, `department_name`,
  `job_function`, `job_title`, `email`, `user_principal_name`,
  `sam_account_name`, `report_to_email`, `report_to_sam_account_name`.

- [ ] **Step 1: Create the macro**

```sql
{%- macro tableau_access_columns(roster_alias, crosswalk_alias) -%}
    {{ crosswalk_alias }}.location_clean_name as location_name,
    {{ crosswalk_alias }}.campus_name,

    {{ roster_alias }}.home_business_unit_name as entity,
    {{ roster_alias }}.home_department_name as department_name,
    {{ roster_alias }}.job_function,
    {{ roster_alias }}.job_title,

    {{ roster_alias }}.mail as email,
    {{ roster_alias }}.user_principal_name,
    {{ roster_alias }}.sam_account_name,

    {{ roster_alias }}.reports_to_mail as report_to_email,
    {{ roster_alias }}.reports_to_sam_account_name as report_to_sam_account_name,
{%- endmacro -%}
```

The roster column is `reports_to_sam_account_name` (plural "reports") but the
contract column is `report_to_sam_account_name` (singular), matching what every
existing Tableau calc already references. The alias is mandatory — dropping it
renames the column and breaks all 13 workbooks.

- [ ] **Step 2: Verify it compiles in isolation**

Run:

```bash
uv run dbt compile \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__content_team
```

Expected: PASS (the macro is not yet called, so this only proves nothing broke).

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster add src/dbt/kipptaf/macros/tableau_access_columns.sql
git -C /workspaces/teamster commit -m "feat(dbt): add tableau_access_columns macro

Refs #4638"
```

---

### Task 2: First caller — `rpt_tableau__content_team`

This is the reference implementation. Every later model task follows the same
shape, so get it right here.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__content_team.sql` (49
  lines; roster alias is `srh`, aliases `entity` at line 24 and `` `location` ``
  at line 25)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__content_team.yml`

**Interfaces:**

- Consumes: `tableau_access_columns` from Task 1.
- Produces: the eleven contract columns on `rpt_tableau__content_team`. Consumed
  by no other model; read directly by the Content Team Dashboard and Miami
  Instructional Rubrics workbooks.

- [ ] **Step 1: Add the crosswalk join**

Add to the model's join list, after the existing
`int_people__staff_roster_history` join:

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Replace the ad-hoc aliases with the macro**

Delete the existing `srh.home_business_unit_name as entity,` and
``srh.home_work_location_name as `location`,`` lines, plus any existing
`job_title` or `department` alias in the same select list, and insert:

```sql
    {{ tableau_access_columns("srh", "lc") }}
```

Leaving the old `entity` or `job_title` aliases in place will produce a
duplicate column name and fail the build.

- [ ] **Step 3: Build the model and confirm it fails or passes loudly**

Run:

```bash
uv run dbt build \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__content_team --target dev
```

Expected: PASS. A duplicate-column error here means Step 2 missed an old alias.

- [ ] **Step 4: Verify the location values are clean names, not raw**

Run:

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select distinct location_name, entity from {{ ref('rpt_tableau__content_team') }} order by 2, 1" \
  --limit 50 --target dev
```

Expected: values like `KIPP Hatch Middle` and `KIPP Sumner Elementary` (clean
names). Seeing `KIPP Hatch Academy` means the raw column is still being emitted.

- [ ] **Step 5: Document the new columns in the properties YAML**

Add to `columns:` in `properties/rpt_tableau__content_team.yml`:

```yaml
- name: location_name
  data_type: string
  description: >-
    Canonical location from int_people__location_crosswalk. Drives the Tableau
    location gate. Retired name aliases collapse onto their canonical clean name
    here.
  data_tests:
    - not_null
- name: entity
  data_type: string
  description: >-
    Legal entity from the roster's home_business_unit_name. Drives the Tableau
    entity gate. Never location_region, which is a property of the location
    rather than the person.
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
- name: department_name
  data_type: string
- name: job_function
  data_type: string
- name: email
  data_type: string
  description: Post-cutover Tableau identity; roster mail.
- name: user_principal_name
  data_type: string
- name: report_to_email
  data_type: string
```

- [ ] **Step 6: Re-run the build to pick up the tests**

Run:

```bash
uv run dbt build \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__content_team --target dev
```

Expected: PASS, including the `not_null` and `accepted_values` tests.

- [ ] **Step 7: Lint**

Run:

```bash
cd /workspaces/teamster && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__content_team.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__content_team.yml </dev/null
```

Expected: no sqlfluff or yamllint issues.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__content_team.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__content_team.yml
git -C /workspaces/teamster commit -m "feat(dbt): apply tableau access contract to content_team

Refs #4638"
```

---

### Tasks 3-9: Remaining models with an existing roster join

**Read Task 2 in full before starting any of these.** Each of these tasks
executes Task 2's eight steps verbatim — add the crosswalk join, replace the
ad-hoc aliases with `{{ tableau_access_columns(...) }}`, add the YAML column
entries from Task 2 Step 5, build, lint, commit. The table below gives only the
per-model deltas: the file, the roster alias, and which old aliases to delete.

Do not batch them into one commit; one model per commit so a reviewer can reject
one without rejecting all.

| Task | Model                                              | Roster alias    | Old aliases to delete                                       | Notes                                                                                                                                       |
| ---- | -------------------------------------------------- | --------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 3    | `rpt_tableau__leadership_development`              | `r`             | `entity` (L121), `` `location` `` (L122)                    |                                                                                                                                             |
| 4    | `rpt_tableau__schoolmint_grow_goals`               | `srh`           | `entity` (L4), `` `location` `` (L5)                        |                                                                                                                                             |
| 5    | `rpt_tableau__schoolmint_grow_observation_details` | `srh`           | `entity` + `` `location` `` at **both** L29-30 and L185-186 | Two select blocks; both need the macro and both need the crosswalk join                                                                     |
| 6    | `rpt_tableau__teacher_observations`                | `rh`            | `entity` + `` `location` `` at **both** L69-70 and L134-135 | Two select blocks                                                                                                                           |
| 7    | `rpt_tableau__survey_responses`                    | `eh`            | `legal_entity` (L21), `` `location` `` (L24)                | Alias is `legal_entity`, not `entity` — downstream `rpt_tableau__survey_completion` selects it, so Task 10 must be updated in the same push |
| 8    | `rpt_tableau__operations_ekg`                      | see note        | `respondent_location` (L7), `region`                        | Already joins the crosswalk; reuse the existing alias rather than adding a second join                                                      |
| 9    | `rpt_tableau__operations_pm`                       | `ops_pm_roster` | `region`                                                    | Already joins the crosswalk via `schools`; reuse it                                                                                         |

For Tasks 5 and 6, verify **both** blocks emit the contract columns:

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select count(*) as rows_missing_location from {{ ref('rpt_tableau__schoolmint_grow_observation_details') }} where location_name is null" \
  --target dev
```

Expected: `0`. A non-zero count means one block was missed.

---

### Task 10: `rpt_tableau__survey_completion` — inherited columns

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_completion.sql`
  (48 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_completion.yml`

**Interfaces:**

- Consumes: `rpt_tableau__survey_responses` contract columns from Task 7.
- Produces: the eleven contract columns on `rpt_tableau__survey_completion`.

This model has no roster join. It selects `sl.location`, `sl.business_unit`, and
`sl.mail` from `rpt_tableau__survey_links`, which is **out of scope** per the
global constraints. So the contract columns come from a roster join added here.

- [ ] **Step 1: Add roster and crosswalk joins**

Add after the existing `deduplicate as sr` join:

```sql
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on sl.employee_number = sr2.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr2.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Replace the inherited columns with the macro**

Delete `sl.business_unit,`, `sl.location,`, `sl.department,`, `sl.job_title,`
and `sl.mail,` from the select list, then add:

```sql
    {{ tableau_access_columns("sr2", "lc") }}
```

- [ ] **Step 3: Build**

Run:

```bash
uv run dbt build \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__survey_completion --target dev
```

Expected: PASS.

- [ ] **Step 4: Confirm the row count did not change**

The added joins must not fan out. Run:

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select count(*) as ct, count(distinct format('%T|%T|%T', employee_number, academic_year, survey_round)) as distinct_key from {{ ref('rpt_tableau__survey_completion') }}" \
  --target dev
```

Expected: `ct` equals `distinct_key`. If `ct` is larger,
`int_people__staff_roster` returned more than one row per `employee_number` and
the join needs a `is_current` predicate.

- [ ] **Step 5: Document, lint, and commit**

Follow Task 2 Steps 5, 7, and 8, substituting this model's paths.

---

### Task 11: `rpt_tableau__stipend_and_bonus_app`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__stipend_and_bonus_app.sql`
  (35 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__stipend_and_bonus_app.yml`

**Interfaces:**

- Consumes: `tableau_access_columns` from Task 1.
- Produces: the eleven contract columns.

Location and entity currently come from `rpt_appsheet__stipend_app_roster` as
`r.location` and `r.entity`. That roster is out of scope, so add a direct roster
join keyed on the subject employee. Note `r1` and `r2` already alias
`int_people__staff_roster` for the two approvers — use `r3` to avoid collision.

- [ ] **Step 1: Add roster and crosswalk joins**

```sql
left join
    {{ ref("int_people__staff_roster") }} as r3
    on o.employee_number = r3.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on r3.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Replace the passthrough columns with the macro**

Delete `r.job_title,`, `r.department,`, `r.location,`, `r.entity,` and add:

```sql
    {{ tableau_access_columns("r3", "lc") }}
```

Keep `r.entity_short`, `r.position_id`, `r.formatted_name as teammate`, and
`r.payroll_group_code as company_code` — they are not contract columns.

- [ ] **Step 3: Build, verify no fan-out, document, lint, commit**

Follow Task 10 Steps 3-5, substituting this model's paths and using `event_id`
as the distinct key in the fan-out check.

---

### Task 12: `rpt_tableau__grants_timesheets`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__grants_timesheets.sql`
  (53 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__grants_timesheets.yml`

**Interfaces:**

- Consumes: `tableau_access_columns` from Task 1.
- Produces: the eleven contract columns describing the **respondent** — the
  person certifying their own time.

This model has no roster join and no `mail`. Its columns come from an Alchemer
source with `respondent_*` prefixes. Existing `respondent_*` columns stay; the
contract columns are added alongside and describe the same person.

- [ ] **Step 1: Add roster and crosswalk joins inside the `sub` CTE**

```sql
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on ri.respondent_employee_number = sr2.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr2.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Add the macro columns to the `sub` CTE select list**

```sql
    {{ tableau_access_columns("sr2", "lc") }}
```

- [ ] **Step 3: Pass the contract columns through the outer select**

The outer select enumerates columns explicitly, so add each of the eleven by
name after `respondent_primary_job`:

```sql
    location_name,
    campus_name,
    entity,
    department_name,
    job_function,
    job_title,
    email,
    user_principal_name,
    sam_account_name,
    report_to_email,
    report_to_sam_account_name,
```

The `pivot` operates on `sub`, so any column not listed in the outer select is
dropped silently — this step is why the model needs its own verification.

- [ ] **Step 4: Verify the columns survived the pivot**

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select location_name, entity, email from {{ ref('rpt_tableau__grants_timesheets') }} limit 5" \
  --target dev
```

Expected: three populated columns. A "column not found" error means Step 3 was
skipped or the pivot dropped them.

- [ ] **Step 5: Build, document, lint, commit**

Follow Task 2 Steps 3, 5, 7, and 8.

---

### Task 13: `rpt_tableau__pm_outlier_detection` — two location axes

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__pm_outlier_detection.sql`
  (167 lines; `observer_location` at L139, `teacher_location` at L146)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__pm_outlier_detection.yml`

**Interfaces:**

- Consumes: `tableau_access_columns` from Task 1.
- Produces: the eleven contract columns describing **the observed teacher**,
  plus the existing `observer_location` retained under its current name.

This model carries both an observer and an observed teacher. Per the design
decision, access gates on the **teacher's** location. The teacher roster alias
is `sa` (L146); the observer alias is `srh`.

- [ ] **Step 1: Add the crosswalk join keyed on the teacher**

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sa.home_work_location_name = lc.location_name
```

- [ ] **Step 2: Add the macro using the teacher alias**

Replace `sa.home_work_location_name as teacher_location,` with:

```sql
    {{ tableau_access_columns("sa", "lc") }}
```

Leave `srh.home_work_location_name as observer_location,` **unchanged**. It is
not a contract column and renaming it would break existing views.

- [ ] **Step 3: Build and confirm both axes exist**

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select observer_location, location_name from {{ ref('rpt_tableau__pm_outlier_detection') }} limit 5" \
  --target dev
```

Expected: both columns present and populated. `location_name` is the teacher's
canonical location; `observer_location` remains the raw observer value.

- [ ] **Step 4: Document, lint, commit**

Follow Task 2 Steps 5, 7, and 8. In the YAML, state explicitly that
`location_name` describes the observed teacher and gates access, while
`observer_location` is descriptive only.

---

### Task 14: New extract `rpt_tableau__manager_survey_details`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__manager_survey_details.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__manager_survey_details.yml`
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`

**Interfaces:**

- Consumes: `int_surveys__manager_survey_details`, `int_people__staff_roster`,
  `int_people__location_crosswalk`, and `tableau_access_columns` from Task 1.
- Produces: `rpt_tableau__manager_survey_details` with the eleven contract
  columns describing the **subject** (the person being rated), plus every
  existing column from the intermediate model.

The two manager survey workbooks currently read
`int_surveys__manager_survey_details` directly. That model already carries
`subject_samaccountname`, `subject_userprincipalname`, `subject_primary_site`,
and `subject_legal_entity_name`, but no `mail`. This extract wraps it and
applies the contract.

- [ ] **Step 1: Create the model**

```sql
select
    msd.*,

    {{ tableau_access_columns("sr", "lc") }}
from {{ ref("int_surveys__manager_survey_details") }} as msd
left join
    {{ ref("int_people__staff_roster") }} as sr
    on msd.subject_df_employee_number = sr.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
```

Confirm the subject employee-number column name against the intermediate model
before running; if it differs from `subject_df_employee_number`, use the actual
name rather than adding a rename.

- [ ] **Step 2: Build and verify no fan-out**

```bash
uv run dbt build \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__manager_survey_details --target dev
```

Then compare row counts against the intermediate model:

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select (select count(*) from {{ ref('int_surveys__manager_survey_details') }}) as int_ct, (select count(*) from {{ ref('rpt_tableau__manager_survey_details') }}) as rpt_ct" \
  --target dev
```

Expected: `int_ct` equals `rpt_ct`.

- [ ] **Step 3: Add the properties YAML**

Include a model description stating that this extract exists so the manager
survey workbooks depend on an `rpt_` model rather than an intermediate one, and
that the contract columns describe the survey **subject**, not the respondent.
Add the same column entries as Task 2 Step 5.

- [ ] **Step 4: Update the exposures**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, change the
`manager_survey_reports` exposure's `depends_on` from
`ref("int_surveys__manager_survey_details")` to
`ref("rpt_tableau__manager_survey_details")`, and add three new exposures
following the existing file's structure exactly:

- `manager_survey_rollup` depending on
  `ref("rpt_tableau__manager_survey_details")`
- `content_team_dashboard` depending on `ref("rpt_tableau__content_team")`
- `teacher_goals` depending on the model confirmed from the workbook (see
  Task 16)

- [ ] **Step 5: Lint and commit**

Follow Task 2 Steps 7 and 8, including `exposures/tableau.yml` in the `git add`.

---

### Task 15: Cross-model invariant tests

**Files:**

- Create:
  `src/dbt/kipptaf/tests/assert_roster_locations_resolve_to_crosswalk.sql`
- Create: `src/dbt/kipptaf/tests/assert_tableau_location_name_set_expected.sql`

**Interfaces:**

- Consumes: `int_people__staff_roster`, `int_people__location_crosswalk`,
  `rpt_tableau__content_team`.
- Produces: two singular tests. No model consumes these.

These catch the failure mode the whole rebuild exists to eliminate: a new school
or a renamed location silently resolving to no group.

- [ ] **Step 1: Write the coverage test**

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

- [ ] **Step 2: Run it and confirm it passes today**

```bash
uv run dbt test \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select assert_roster_locations_resolve_to_crosswalk --target dev
```

Expected: PASS with 0 rows. This was verified against production data on
2026-07-30 — 100% of active staff resolved.

- [ ] **Step 3: Write the expected-value-set test**

```sql
-- The gated location values are a known set of 30. An addition should fail
-- loudly here rather than silently gate to nothing in Tableau.
with expected as (
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

- [ ] **Step 4: Run it**

```bash
uv run dbt test \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select assert_tableau_location_name_set_expected --target dev
```

Expected: PASS. If it fails with a count other than 30, a location was added or
removed — update the Tableau block and the expected count together, and say
which in the commit message.

- [ ] **Step 5: Write the identity-coverage test**

Create `src/dbt/kipptaf/tests/assert_staff_email_populated_with_sam.sql`. This
is `warn`-level, not `error` — one active record legitimately has neither value
today, so failing the build would block every future run.

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

- [ ] **Step 6: Run it**

```bash
uv run dbt test \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select assert_staff_email_populated_with_sam --target dev
```

Expected: WARN with 0 or 1 rows, not an error. A count above 1 means new records
lost their mail value and Tier 1 will fail for them.

- [ ] **Step 7: Lint and commit**

Follow Task 2 Steps 7 and 8.

---

### Task 16: Confirm the two unknown datasources

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` (only if Task 14 Step 4
  left `teacher_goals` unresolved)

**Interfaces:**

- Consumes: nothing.
- Produces: a confirmed model name for the `teacher_goals` exposure.

Teacher Goals and Manager Survey Rollup have no exposure, so their backing
models were inferred rather than confirmed. Guessing here would put a wrong
dependency in the DAG.

- [ ] **Step 1: Read the workbook datasources from Tableau**

Use the Tableau MCP: `list-workbooks` filtered to `name:eq:Teacher Goals`, then
`get-view` on its `defaultViewId` to read upstream datasources.

- [ ] **Step 2: Map each datasource to its dbt model**

Match the datasource name against `models/exposures/tableau.yml`. If it maps to
a model already covered by Tasks 2-14, no dbt change is needed — only the
exposure.

- [ ] **Step 3: If it maps to an uncovered model, stop and report**

An uncovered model means the contract has a gap and the plan needs a new task.
Report the model name rather than improvising a fix.

- [ ] **Step 4: Add the exposure and commit**

Follow Task 14 Step 4's structure, then Task 2 Step 8.

---

### Task 17: Full-selection build and push

**Files:** none modified.

**Interfaces:**

- Consumes: every prior task.
- Produces: a pushed branch ready for CI and review.

- [ ] **Step 1: Build every touched model together**

```bash
uv run dbt build \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --select rpt_tableau__content_team rpt_tableau__leadership_development \
    rpt_tableau__schoolmint_grow_goals rpt_tableau__schoolmint_grow_observation_details \
    rpt_tableau__teacher_observations rpt_tableau__survey_responses \
    rpt_tableau__survey_completion rpt_tableau__operations_ekg rpt_tableau__operations_pm \
    rpt_tableau__stipend_and_bonus_app rpt_tableau__grants_timesheets \
    rpt_tableau__pm_outlier_detection rpt_tableau__manager_survey_details \
  --target dev
```

Expected: all models and tests PASS.

- [ ] **Step 2: Confirm every model emits the contract columns**

For each of the 13, run:

```bash
uv run dbt show \
  --project-dir /workspaces/teamster/src/dbt/kipptaf \
  --inline "select location_name, entity, email, job_function from {{ ref('<model>') }} limit 1" \
  --target dev
```

Expected: no "column not found" errors. This is the check that proves the
contract actually holds, and it is the precondition for any Tableau edit.

- [ ] **Step 3: Lint every changed file**

```bash
cd /workspaces/teamster && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C . diff --name-only origin/main...HEAD | grep -E '\.(sql|yml)$' | xargs -I{} test -f {} && git -C . diff --name-only origin/main...HEAD | grep -E '\.(sql|yml)$') </dev/null
```

Expected: no issues. Filter to existing paths — a `--force` check over a deleted
path hard-errors.

- [ ] **Step 4: Push and report**

```bash
git -C /workspaces/teamster push -u origin cristinabaldor/feat/claude-tableau-rls-entra-migration
```

Then report the branch name and stop. Do **not** open the PR — the Tableau half
is not done, and a PR implies the workbooks are ready.

---

## Out of scope for this plan

The Tableau remediation — the canonical Permissions block, the per-workbook
helper field, the 13 workbook edits, the Preview as User persona matrix, and the
`entra-ready` tagging — is a separate plan, executed by a human in Tableau
Desktop, and depends on this one being merged and built first.

Also excluded, per the design doc: renaming canonical clean names upstream,
populating `job_function` for the 25 unclassified teachers, and the People
Operations data fixes.
