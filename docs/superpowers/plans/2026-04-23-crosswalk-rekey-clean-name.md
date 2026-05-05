# Rekey Crosswalks on `location_clean_name` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rekey five Google Sheet crosswalks (coupa address, coupa intacct
program, coupa user exceptions, egencia, zendesk) on `location_clean_name`, add
missing uniqueness tests, switch `int_people__leadership_crosswalk` to group on
clean name, and update ten downstream SQL consumers.

**Architecture:** Sheet columns renamed from raw-ADP keys to
`location_clean_name`. Downstream consumers swap their join column to
`home_work_location_reporting_name` (already carried by
`int_people__staff_roster` / `_history`). One intermediate model
(`int_people__leadership_crosswalk`) gets re-grouped on clean name so ADP
renames don't split a logical school in two.

**Tech Stack:** dbt Core (BigQuery dialect), Google Sheets external tables, dbt
Cloud CI for test execution.

**Spec:**
[docs/superpowers/specs/2026-04-23-crosswalk-rekey-clean-name-design.md](../specs/2026-04-23-crosswalk-rekey-clean-name-design.md)

**Issue:** [#3728](https://github.com/TEAMSchools/teamster/issues/3728)

---

## Context for the implementer

- Work inside the worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-crosswalk-clean-name`.
  Always `cd` there before running `git` commands.
- `uv run` is required for all Python tools. Never invoke `dbt` / `python3` /
  `python` directly.
- Trunk auto-formats on Write/Edit via PostToolUse hook. Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --ci` from the worktree root.
- dbt cannot be executed locally in this Codespace (no warehouse creds).
  Validation happens in dbt Cloud CI after push.
- External source changes require manual staging via
  `uv run dbt run-operation stage_external_sources --target staging` (run by the
  developer after SQL/YAML land on the PR branch).
- Sheet column renames happen **at merge time**, not during PR development. CI
  will fail on any test that reads a renamed column until the sheet is updated —
  expected.
- Column naming convention: `location_clean_name` (lowercase snake_case)
  uniformly across all renamed sheets.
- Uniqueness test syntax requires `arguments:` nesting (dbt 1.11+), per
  `src/dbt/CLAUDE.md`.
- Commit style: conventional commits, use `git add -u` (never `-A` or `.`).
  HEREDOC for messages per `.claude/CLAUDE.md`.

---

### Task 1: Coupa — three sheets + `rpt_coupa__users`

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__address_name_crosswalk.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__intacct_program_lookup.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__user_exceptions.yml`
- Modify: `src/dbt/kipptaf/models/extracts/coupa/rpt_coupa__users.sql`

- [ ] **Step 1: Update three coupa source entries in `sources-external.yml`**

Find `src_google_sheets__coupa__address_name_crosswalk` (near line 612) and set
its `columns:` to:

```yaml
columns:
  - name: location_clean_name
    data_type: string
  - name: coupa_address_name
    data_type: string
```

Find `src_google_sheets__coupa__user_exceptions` (near line 682) and set its
`columns:` to:

```yaml
columns:
  - name: employee_number
    data_type: int64
  - name: coupa_school_name
    data_type: string
  - name: location_clean_name
    data_type: string
  - name: sage_intacct_department
    data_type: int64
```

Find `src_google_sheets__coupa__intacct_program_lookup` (near line 708) and set
its `columns:` to:

```yaml
columns:
  - name: adp_business_unit_home_code
    data_type: string
  - name: location_clean_name
    data_type: string
  - name: sage_intacct_program
    data_type: int64
  - name: sage_intacct_location
    data_type: int64
```

- [ ] **Step 2: Rewrite `stg_google_sheets__coupa__address_name_crosswalk.yml`**

```yaml
models:
  - name: stg_google_sheets__coupa__address_name_crosswalk
    description: |
      Crosswalk from canonical `location_clean_name` to Coupa's address name.
      Sourced from a Google Sheet maintained by the People team.
    columns:
      - name: location_clean_name
        description: |
          Canonical location name from `int_people__location_crosswalk`. Join
          key to `int_people__staff_roster.home_work_location_reporting_name`.
        data_type: string
        data_tests:
          - unique
      - name: coupa_address_name
        description: Address name as it appears in Coupa's address book.
        data_type: string
```

- [ ] **Step 3: Rewrite `stg_google_sheets__coupa__user_exceptions.yml`**

```yaml
models:
  - name: stg_google_sheets__coupa__user_exceptions
    description: |
      Per-employee Coupa override sheet — lets the Finance team pin an
      employee to a specific school / location / department regardless of
      their ADP assignment. Sourced from a Google Sheet maintained by Finance.
    columns:
      - name: employee_number
        description: ADP employee number (HRIS employee ID).
        data_type: int64
        data_tests:
          - unique
      - name: coupa_school_name
        description: Override school name for Coupa user record.
        data_type: string
      - name: location_clean_name
        description: |
          Override canonical location name from `int_people__location_crosswalk`.
          Used in the coalesce chain against `home_work_location_reporting_name`.
        data_type: string
      - name: sage_intacct_department
        description: Override Sage Intacct department ID.
        data_type: int64
```

- [ ] **Step 4: Rewrite `stg_google_sheets__coupa__intacct_program_lookup.yml`**

```yaml
models:
  - name: stg_google_sheets__coupa__intacct_program_lookup
    description: |
      Lookup from ADP business unit + canonical location to Sage Intacct
      program and location codes. Sourced from a Google Sheet maintained by
      Finance.
    columns:
      - name: adp_business_unit_home_code
        description: ADP `home_business_unit` code.
        data_type: string
      - name: location_clean_name
        description: |
          Canonical location name from `int_people__location_crosswalk`. Join
          key to `int_people__staff_roster.home_work_location_reporting_name`.
          The literal value `'Default'` is used for the fallback row.
        data_type: string
      - name: sage_intacct_program
        description: Sage Intacct program code.
        data_type: int64
      - name: sage_intacct_location
        description: Sage Intacct location code.
        data_type: int64
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - adp_business_unit_home_code
              - location_clean_name
```

- [ ] **Step 5: Update `rpt_coupa__users.sql` CTE passthrough (lines 39, 84)**

In the `all_users` CTE (both branches of the UNION ALL), replace the column pull
so that `home_work_location_name` inside the file now holds the clean value:

Line 39 — replace:

```sql
sr.home_work_location_name,
```

with:

```sql
sr.home_work_location_reporting_name as home_work_location_name,
```

Line 84 — same replacement:

```sql
sr.home_work_location_reporting_name as home_work_location_name,
```

(This preserves every downstream reference to `home_work_location_name` in the
file as-is; only its value changes from raw ADP to clean name.)

- [ ] **Step 6: Update `rpt_coupa__users.sql` user-exceptions override column
      (line 179)**

Replace:

```sql
on coalesce(x.home_work_location_name, au.home_work_location_name)
= anc.adp_home_work_location_name
```

with:

```sql
on coalesce(x.location_clean_name, au.home_work_location_name)
= anc.location_clean_name
```

- [ ] **Step 7: Update `rpt_coupa__users.sql` intacct_program joins (lines
      294, 298)**

Replace line 294:

```sql
and sub.home_work_location_name = ipl1.adp_home_work_location_name
```

with:

```sql
and sub.home_work_location_name = ipl1.location_clean_name
```

Replace line 298:

```sql
and ipl2.adp_home_work_location_name = 'Default'
```

with:

```sql
and ipl2.location_clean_name = 'Default'
```

(Note: `sub.home_work_location_name` already holds the clean value thanks to
Step 5.)

- [ ] **Step 8: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci \
    src/dbt/kipptaf/models/google/sheets/sources-external.yml \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__address_name_crosswalk.yml \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__user_exceptions.yml \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__coupa__intacct_program_lookup.yml \
    src/dbt/kipptaf/models/extracts/coupa/rpt_coupa__users.sql
```

Expected: `No issues`.

- [ ] **Step 9: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-crosswalk-clean-name
git add -u
git commit -m "$(cat <<'EOF'
refactor(dbt,coupa): rekey coupa crosswalks on location_clean_name

Refs #3728. Rekeys address_name_crosswalk, intacct_program_lookup, and
user_exceptions on location_clean_name. rpt_coupa__users CTE now
passes home_work_location_reporting_name through as the internal
home_work_location_name column so the three crosswalk joins resolve
against clean name. Adds missing uniqueness tests to all three staging
models.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Egencia

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__egencia__traveler_groups.yml`
- Modify: `src/dbt/kipptaf/models/extracts/egencia/rpt_egencia__users.sql`

- [ ] **Step 1: Update egencia source entry in `sources-external.yml`**

Find `src_google_sheets__egencia__traveler_groups` (near line 429). Replace the
`columns:` list with:

```yaml
columns:
  - name: adp_home_business_unit_name
    data_type: string
  - name: location_clean_name
    data_type: string
  - name: adp_department_home_name
    data_type: string
  - name: adp_job_title
    data_type: string
  - name: egencia_traveler_group
    data_type: string
```

- [ ] **Step 2: Rewrite `stg_google_sheets__egencia__traveler_groups.yml`**

```yaml
models:
  - name: stg_google_sheets__egencia__traveler_groups
    description: |
      Cascading lookup from ADP org / job attributes to Egencia traveler
      group. Sourced from a Google Sheet maintained by Finance.
    columns:
      - name: adp_home_business_unit_name
        description: ADP `home_business_unit` code for the traveler.
        data_type: string
      - name: location_clean_name
        description: |
          Canonical location name from `int_people__location_crosswalk`. Join
          key to `int_people__staff_roster.home_work_location_reporting_name`.
        data_type: string
      - name: adp_department_home_name
        description: ADP `home_department` name for the traveler.
        data_type: string
      - name: adp_job_title
        description: ADP `job_title` for the traveler.
        data_type: string
      - name: egencia_traveler_group
        description: Traveler group assignment in Egencia.
        data_type: string
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - adp_home_business_unit_name
              - location_clean_name
              - adp_department_home_name
              - adp_job_title
```

- [ ] **Step 3: Update `rpt_egencia__users.sql` joins (lines 30, 36, 42)**

In each of the three cascading join tiers, replace the RHS and LHS of the
location-name match:

Line 30 — replace:

```sql
and sr.home_work_location_name = tg.adp_home_work_location_name
```

with:

```sql
and sr.home_work_location_reporting_name = tg.location_clean_name
```

Line 36 — same pattern for `tg2`:

```sql
and sr.home_work_location_reporting_name = tg2.location_clean_name
```

Line 42 — same pattern for `tg3`:

```sql
and sr.home_work_location_reporting_name = tg3.location_clean_name
```

- [ ] **Step 4: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci \
    src/dbt/kipptaf/models/google/sheets/sources-external.yml \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__egencia__traveler_groups.yml \
    src/dbt/kipptaf/models/extracts/egencia/rpt_egencia__users.sql
```

Expected: `No issues`.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "$(cat <<'EOF'
refactor(dbt,egencia): rekey traveler groups on location_clean_name

Refs #3728. Renames sheet column and swaps rpt_egencia__users joins to
sr.home_work_location_reporting_name. Adds composite uniqueness test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Zendesk

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__zendesk_org_lookup.yml`
- Modify: `src/dbt/kipptaf/models/extracts/zendesk/rpt_zendesk__users.sql`

- [ ] **Step 1: Update zendesk source entry in `sources-external.yml`**

Find `src_google_sheets__zendesk__org_lookup` (near line 8). Replace the
`columns:` list with:

```yaml
columns:
  - name: adp_business_unit
    data_type: string
  - name: location_clean_name
    data_type: string
  - name: zendesk_organization
    data_type: string
  - name: zendesk_secondary_location
    data_type: string
```

(Sheet owner must also snake_case the sheet headers to match.)

- [ ] **Step 2: Rewrite `stg_google_sheets__zendesk_org_lookup.yml`**

```yaml
models:
  - name: stg_google_sheets__zendesk_org_lookup
    description: |
      Lookup from ADP business unit + canonical location to Zendesk
      organization. Sourced from a Google Sheet maintained by IT.
    columns:
      - name: adp_business_unit
        description: ADP `home_business_unit` code for the staff member.
        data_type: string
      - name: location_clean_name
        description: |
          Canonical location name from `int_people__location_crosswalk`. Join
          key to `int_people__staff_roster.home_work_location_reporting_name`.
        data_type: string
      - name: zendesk_organization
        description: Organization name in Zendesk.
        data_type: string
      - name: zendesk_secondary_location
        description: Secondary location attribute for the Zendesk user record.
        data_type: string
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - adp_business_unit
              - location_clean_name
```

- [ ] **Step 3: Update `rpt_zendesk__users.sql` CTE source + join**

Line 8 — replace:

```sql
sr.home_work_location_name as adp__home_work_location_name,
```

with:

```sql
sr.home_work_location_reporting_name as adp__home_work_location_name,
```

Line 46 — replace:

```sql
and sr.adp__home_work_location_name = zol.adp_location
```

with:

```sql
and sr.adp__home_work_location_name = zol.location_clean_name
```

**Do not change line 94** (the final `SELECT adp__home_work_location_name`) —
that output column name is a Zendesk ingestion contract.

- [ ] **Step 4: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci \
    src/dbt/kipptaf/models/google/sheets/sources-external.yml \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__zendesk_org_lookup.yml \
    src/dbt/kipptaf/models/extracts/zendesk/rpt_zendesk__users.sql
```

Expected: `No issues`.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "$(cat <<'EOF'
refactor(dbt,zendesk): rekey zendesk org lookup on location_clean_name

Refs #3728. Renames sheet column and swaps rpt_zendesk__users join to
home_work_location_reporting_name. Preserves output column
adp__home_work_location_name (Zendesk ingestion contract). Adds
composite uniqueness test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Campus crosswalk + clever/illuminate/ddi downstream

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__campus_crosswalk.yml`
- Modify: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql`
- Modify: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql`
- Modify: `src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`

No sheet column rename — `Name` is used by other consumers as a rollup key.
Instead downstream consumers switch to `Location_Name` which already holds the
clean name.

- [ ] **Step 1: Rewrite `stg_google_sheets__people__campus_crosswalk.yml`**

```yaml
models:
  - name: stg_google_sheets__people__campus_crosswalk
    description: |
      Campus roll-up crosswalk — maps each campus `name` to the canonical
      location it belongs to, along with school-level metadata. Sourced from
      a Google Sheet maintained by the People team.
    columns:
      - name: name
        description: Campus name (distinct from location_name).
        data_type: string
      - name: location_name
        description: |
          Canonical location name from `int_people__location_crosswalk`. Join
          key to `int_people__staff_roster.home_work_location_reporting_name`.
        data_type: string
      - name: region
        description: Region the campus belongs to.
        data_type: string
      - name: grade_band
        description: Grade band the campus serves.
        data_type: string
      - name: powerschool_school_id
        description: PowerSchool `school_id` for the campus.
        data_type: int64
      - name: reporting_school_id
        description: Stable reporting ID for the campus.
        data_type: int64
      - name: abbreviation
        description: Short code / abbreviation for the campus.
        data_type: string
      - name: is_pathways
        description: Whether the campus is part of the Pathways program.
        data_type: boolean
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - name
              - is_pathways
```

- [ ] **Step 2: Update `rpt_clever__staff.sql` (line 74)**

Replace:

```sql
on sr.home_work_location_name = ccw.name
```

with:

```sql
on sr.home_work_location_reporting_name = ccw.location_name
```

- [ ] **Step 3: Update `rpt_clever__sections.sql` (line 12)**

Replace:

```sql
on sr.home_work_location_name = ccw.name
```

with:

```sql
on sr.home_work_location_reporting_name = ccw.location_name
```

- [ ] **Step 4: Update `rpt_illuminate__roles.sql` (line 48)**

Replace:

```sql
on sr.home_work_location_name = cc.name
```

with:

```sql
on sr.home_work_location_reporting_name = cc.location_name
```

- [ ] **Step 5: Update `rpt_tableau__ddi_dashboard.sql` (line 523 only)**

Replace:

```sql
on r.home_work_location_name = cw.name
```

with:

```sql
on r.home_work_location_reporting_name = cw.location_name
```

**Do not touch line 25** (`on il.school = cw.name`) — that join matches an
illuminate column against the campus name, unrelated to the ADP-lookup pattern.

- [ ] **Step 6: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci \
    src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__campus_crosswalk.yml \
    src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql \
    src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql \
    src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql \
    src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql
```

Expected: `No issues`.

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "$(cat <<'EOF'
refactor(dbt): swap campus-crosswalk ADP joins to location_clean_name

Refs #3728. Switches clever, illuminate, and ddi_dashboard joins from
ccw.name to ccw.location_name via sr.home_work_location_reporting_name.
Adds uniqueness test to campus_crosswalk staging model.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `int_people__leadership_crosswalk` regroup + three consumers

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__leadership_crosswalk.sql`
- Modify:
  `src/dbt/kipptaf/models/people/intermediate/properties/int_people__leadership_crosswalk.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__pm_assignment_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__renewal_status.sql`

The model currently `GROUP BY`s raw ADP `home_work_location_name`. Switch to
grouping on `home_work_location_reporting_name`. Emit the clean value as the new
canonical column; rename the existing output column so consumers update in
lockstep with the same commit.

- [ ] **Step 1: Rewrite `int_people__leadership_crosswalk.sql`**

Replace every occurrence of `home_work_location_name` with
`home_work_location_reporting_name` inside this file. The full updated file:

```sql
with
    staff_roster as (
        select
            employee_number,
            formatted_name,
            mail,
            sam_account_name,
            google_email,
            job_title,
            home_work_location_reporting_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name,
            reports_to_employee_number,
        from {{ ref("int_people__staff_roster") }}
        where
            job_title in (
                'Director School Operations',
                'Director Campus Operations',
                'Managing Director of Operations',
                'School Leader',
                'School Leader in Residence'
            )
            and assignment_status != 'Terminated'
            and home_work_location_powerschool_school_id != 0
    ),

    school_leadership as (
        select
            home_work_location_reporting_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name,

            coalesce(
                max(
                    if(job_title = 'Director School Operations', employee_number, null)
                ),
                max(if(job_title = 'Director Campus Operations', employee_number, null))
            ) as dso_employee_number,

            coalesce(
                max(if(job_title = 'School Leader', employee_number, null)),
                max(if(job_title = 'School Leader in Residence', employee_number, null))
            ) as sl_employee_number,
        from staff_roster
        group by
            home_work_location_reporting_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name
    ),

    mdo as (
        select
            home_work_location_region,

            max(
                if(job_title = 'Managing Director of Operations', employee_number, null)
            ) as mdo_employee_number,
        from staff_roster
        group by home_work_location_region
    )

select
    l.home_work_location_powerschool_school_id,
    l.home_work_location_reporting_name,
    l.home_work_location_abbreviation,
    l.home_work_location_campus_name,
    l.dso_employee_number,
    l.sl_employee_number,

    sl.formatted_name as school_leader_preferred_name_lastfirst,
    sl.mail as school_leader_mail,
    sl.google_email as school_leader_google_email,
    sl.job_title as school_leader_job_title,
    sl.reports_to_employee_number as school_leader_report_to_employee_number,
    sl.sam_account_name as school_leader_sam_account_name,

    hos.employee_number as head_of_school_employee_number,
    hos.formatted_name as head_of_school_preferred_name_lastfirst,
    hos.mail as head_of_school_mail,
    hos.google_email as head_of_school_google_email,
    hos.job_title as head_of_school_job_title,
    hos.sam_account_name as head_of_school_sam_account_name,

    dso.formatted_name as dso_preferred_name_lastfirst,
    dso.mail as dso_mail,
    dso.google_email as dso_google_email,
    dso.job_title as dso_job_title,
    dso.reports_to_employee_number as dso_report_to_employee_number,
    dso.sam_account_name as dso_sam_account_name,

    mdso.employee_number as mdso_employee_number,
    mdso.formatted_name as mdso_preferred_name_lastfirst,
    mdso.mail as mdso_mail,
    mdso.google_email as mdso_google_email,
    mdso.job_title as mdso_job_title,
    mdso.sam_account_name as mdso_sam_account_name,

    mdo.employee_number as mdo_employee_number,
    mdo.formatted_name as mdo_preferred_name_lastfirst,
    mdo.mail as mdo_mail,
    mdo.google_email as mdo_google_email,
    mdo.job_title as mdo_job_title,
    mdo.sam_account_name as mdo_sam_account_name,
from school_leadership as l
left join staff_roster as sl on l.sl_employee_number = sl.employee_number
left join staff_roster as hos on sl.reports_to_employee_number = hos.employee_number
left join staff_roster as dso on l.dso_employee_number = dso.employee_number
left join staff_roster as mdso on dso.reports_to_employee_number = mdso.employee_number
left join mdo as m on l.home_work_location_region = m.home_work_location_region
left join staff_roster as mdo on m.mdo_employee_number = mdo.employee_number
```

- [ ] **Step 2: Update `int_people__leadership_crosswalk.yml`**

Find the column entry for `home_work_location_name` and rename it to
`home_work_location_reporting_name`. Update its description to reflect the
clean-name semantics. Leave all other column entries untouched. If the YAML has
a uniqueness test keyed on `home_work_location_name`, rename the reference there
too.

- [ ] **Step 3: Update `rpt_tableau__staff_roster.sql` (line 85)**

Replace:

```sql
on b.home_work_location_name = lc.home_work_location_name
```

with:

```sql
on b.home_work_location_reporting_name = lc.home_work_location_reporting_name
```

- [ ] **Step 4: Update `rpt_gsheets__pm_assignment_roster.sql` (line 72)**

Replace:

```sql
on sr.home_work_location_name = lc.home_work_location_name
```

with:

```sql
on sr.home_work_location_reporting_name = lc.home_work_location_reporting_name
```

Do NOT change line 69 (`on sr.home_work_location_name = cc.location_name`) —
that's the campus_crosswalk join and should also switch per Task 4 pattern:

Replace line 69:

```sql
on sr.home_work_location_name = cc.location_name
```

with:

```sql
on sr.home_work_location_reporting_name = cc.location_name
```

- [ ] **Step 5: Update `int_people__renewal_status.sql` (line 77)**

Replace:

```sql
on h.home_work_location_name = ayl.home_work_location_name
```

with:

```sql
on h.home_work_location_reporting_name = ayl.home_work_location_reporting_name
```

Check lines 26 and 98 in the same file — if they reference
`h.home_work_location_name` or `ayl.home_work_location_name` as display columns
emitted from this model, update those references to
`home_work_location_reporting_name` as well. Do NOT update references to raw ADP
`home_work_location_name` coming from `int_people__staff_roster_history` if the
intent is to preserve the raw display value (likely the case for
`h.home_work_location_name as ay_location` on line 26 — leave that alone).

- [ ] **Step 6: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci \
    src/dbt/kipptaf/models/people/intermediate/int_people__leadership_crosswalk.sql \
    src/dbt/kipptaf/models/people/intermediate/properties/int_people__leadership_crosswalk.yml \
    src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql \
    src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__pm_assignment_roster.sql \
    src/dbt/kipptaf/models/people/intermediate/int_people__renewal_status.sql
```

Expected: `No issues`.

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "$(cat <<'EOF'
refactor(dbt,people): regroup leadership_crosswalk on clean location

Refs #3728. int_people__leadership_crosswalk now groups on
home_work_location_reporting_name so an ADP rename doesn't split one
logical school into two leadership rows. Updates rpt_tableau__staff_roster,
rpt_gsheets__pm_assignment_roster, and int_people__renewal_status to
match the new column.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Operational guide for future ADP renames

**Files:**

- Create: `docs/guides/adp-location-renames.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Create `docs/guides/adp-location-renames.md`**

Use the verbatim guide content from the **Operational guide** section of the
design spec at
`docs/superpowers/specs/2026-04-23-crosswalk-rekey-clean-name-design.md`. That
section already contains the full Scenario 1 / Scenario 2 / What-NOT-to-do
structure. Two adjustments when copying into the guide file:

- Replace "covering two scenarios:" header prelude with a proper H1
  (`# Handling ADP Location Renames`) and a short intro line.
- Expand the Scenario 2 list of sheets to include the two coupa sheets that the
  spec's own Operational Guide section references only in the rollout
  description, so the guide is self-contained:
  - `src_coupa__address_name_crosswalk`
  - `src_coupa__intacct_program_lookup`
  - `src_coupa__user_exceptions`
  - `src_egencia__traveler_groups_v2`
  - zendesk `org_lookup`
  - `src_people__campus_crosswalk` (`Location_Name`)

- [ ] **Step 2: Add guide to mkdocs nav**

In `mkdocs.yml`, locate the `Guides:` section (near line 42). Insert the new
entry alphabetically after `Google Sheets & Forms`:

```yaml
- Guides:
    - guides/index.md
    - Codespaces: guides/codespaces.md
    - Local Development: guides/local-development.md
    - Dagster: guides/dagster.md
    - Google Sheets & Forms: guides/google-sheets.md
    - ADP Location Renames: guides/adp-location-renames.md
    - dbt Development: guides/dbt-development.md
    - SFTP Integration: guides/sftp-integration.md
    - Claude Code & Superpowers: guides/superpowers.md
```

- [ ] **Step 3: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci docs/guides/adp-location-renames.md mkdocs.yml
```

Expected: `No issues`.

- [ ] **Step 4: Commit**

```bash
git add -u docs/guides/adp-location-renames.md mkdocs.yml
git commit -m "$(cat <<'EOF'
docs(guides): add ADP location rename runbook

Refs #3728. New guide covering the two ADP-rename scenarios and the
sheets that need coordinated updates in each.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Stage external, push, open PR, coordinate, verify

**Files:** none (operational steps)

- [ ] **Step 1: Push branch**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-crosswalk-clean-name
git push origin HEAD:cbini/refactor/claude-crosswalk-clean-name
```

- [ ] **Step 2: Stage external sources against staging**

Run in a terminal (requires warehouse creds; cannot run from agent):

```bash
uv run dbt run-operation stage_external_sources \
    --target staging \
    --args '{select: "google_sheets.src_google_sheets__coupa__address_name_crosswalk google_sheets.src_google_sheets__coupa__intacct_program_lookup google_sheets.src_google_sheets__coupa__user_exceptions google_sheets.src_google_sheets__egencia__traveler_groups google_sheets.src_google_sheets__zendesk__org_lookup google_sheets.src_google_sheets__people__campus_crosswalk"}'
```

This refreshes the external-table definitions in BigQuery to match the new YAML
schemas. dbt Cloud CI reads column definitions from BigQuery, not from YAML, so
CI will fail until this runs.

- [ ] **Step 3: Open PR via `mcp__github__create_pull_request`**

Title: `refactor(dbt): rekey downstream crosswalks on location_clean_name`

Body (paste verbatim):

```markdown
## Summary

Closes #3728.

Rekeys five Google Sheet crosswalks (coupa address, coupa intacct program, coupa
user exceptions, egencia, zendesk) on `location_clean_name` and switches
`int_people__leadership_crosswalk` to group on
`home_work_location_reporting_name`, so raw ADP name changes stop propagating
past `int_people__location_crosswalk`. Adds missing uniqueness tests on six
staging models. New operational guide at `docs/guides/adp-location-renames.md`.

See design spec at
`docs/superpowers/specs/2026-04-23-crosswalk-rekey-clean-name-design.md`.

## Sheet owner coordination (at merge)

Before merging, the following sheet owners must rename their sheet columns and
repopulate values with the clean name from `int_people__location_crosswalk`:

- [ ] Coupa `src_coupa__address_name_crosswalk`: `adp_home_work_location_name` →
      `location_clean_name`
- [ ] Coupa `src_coupa__intacct_program_lookup`: `ADP_Home_Work_Location_Name` →
      `location_clean_name`
- [ ] Coupa `src_coupa__user_exceptions`: `home_work_location_name` →
      `location_clean_name`
- [ ] Egencia `src_egencia__traveler_groups_v2`: `adp_home_work_location_name` →
      `location_clean_name`
- [ ] Zendesk `org_lookup`: snake-case all four columns; `ADP_Location` →
      `location_clean_name`
- [ ] People `src_people__campus_crosswalk`: no column renames needed (consumers
      switched to `Location_Name`)

CI will fail on test runs until the sheets are updated. This is expected.

## Test plan

- [ ] dbt Cloud CI passes after sheets are updated and `stage_external_sources`
      is run
- [ ] Row-count parity for all ten affected extracts / intermediate consumers
      (branch vs prod)
- [ ] Confirm next-day downstream sync (coupa user sync, egencia traveler
      groups, zendesk user provisioning, clever roster sync,
      leadership_crosswalk consumers) shows expected deltas
```

- [ ] **Step 4: Link PR in issue**

Use `mcp__github__add_issue_comment` on issue #3728 with body:
`Implementation PR: <PR URL>`.

- [ ] **Step 5: Post-merge verification**

Once sheets are updated and PR merges, run the following query per affected
extract via BigQuery MCP, substituting `<ci_id>` and `<pr_num>` for the dbt
Cloud CI job:

```sql
select 'prod' as env, count(*) as n
from `teamster-332318.kipptaf_extracts.rpt_coupa__users`
union all
select 'pr' as env, count(*) as n
from `teamster-332318.dbt_cloud_pr_<ci_id>_<pr_num>_kipptaf_extracts.rpt_coupa__users`
```

Repeat for: `rpt_egencia__users`, `rpt_zendesk__users`, `rpt_clever__staff`,
`rpt_clever__sections`, `rpt_illuminate__roles`, `rpt_tableau__ddi_dashboard`,
`rpt_tableau__staff_roster`, `rpt_gsheets__pm_assignment_roster`,
`int_people__renewal_status`.

Post results as a final comment on issue #3728. Near-zero deltas confirm the
rekey is clean.
