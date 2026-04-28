# PR Batch C — locations & regions implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the Batch C location/region refactor — new canonical master
sheet, consumer repointing, source-system enrichment, mart `location_key`
migration, address unification on `dim_locations`, `business_unit_code` on
`dim_regions`, and SCD2 boundary normalization on
`dim_work_assignment_locations`.

**Architecture:** Follow the spec at
`docs/superpowers/specs/2026-04-27-batch-c-locations-regions-design.md`. Eight
phases in dependency order: Ops sheet bootstrap → new staging + rename → mart
additions → `int_people__location_crosswalk` rewrite → consumer repointing →
alias-sheet trim → source-system enrichment → mart child fixes.

**Tech Stack:** dbt 1.11+, BigQuery, Google Sheets external sources, dbt-utils,
sqlfluff (BigQuery dialect, 88-char limit, single quotes, trailing commas).

---

## Working conventions

- Always `cd` into the worktree before running commands:
  `cd /workspaces/teamster/.worktrees/cbini-refactor-claude-batch-c-locations-regions`.
- Use `uv run` to invoke dbt — never bare `dbt`.
- After every Edit/Write, formatting runs automatically. Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --ci` from the worktree root.
- Stage with `git add -u` (paths only — never `-A`/`.`).
- Commit messages follow conventional commits with the `dbt` scope.
- After every task, the working tree must build clean:
  `uv run dbt parse --project-dir src/dbt/kipptaf` should succeed.
- For per-model SQL changes, run
  `uv run dbt build --project-dir src/dbt/kipptaf --target staging --select <model>+`
  to validate the model and downstream after edits.
- The full project must `uv run dbt parse` clean before committing each task.
  Tests run in dbt Cloud CI on push.
- After ANY edit to a Google Sheet source, the developer must stage it with
  `--target staging` before the dbt Cloud CI job will pass — this happens off-PR
  (Ops).

---

## Prerequisite: Ops sheet bootstrap (off-PR)

**Owned by Ops, not engineer.** Coordinate before starting Phase 2.

Ops creates a new Google Sheet `src_google_sheets__people__locations` in the
same workbook (`1FCc28XWxFj3gSfItGGJ2tVU0C1fYD1JxKRxuSFqisMo`). Sheet has 38
canonical-grain rows (one per `clean_name` from existing
`src_google_sheets__people__location_crosswalk`).

Columns:

- `location_name` (canonical; matches existing `clean_name`)
- `abbreviation`, `region`, `business_unit`, `grade_band`, `is_campus`,
  `is_pathways`, `dagster_code_location`, `head_of_schools_employee_number`,
  `campus_name`
- `powerschool_school_id`, `deanslist_school_id`, `reporting_school_id`
- `address_line_one`, `address_line_two`, `city`, `postal_code`
- `adp_location_code` (comma-separated for multi-mapped rows like `Room 9` ←
  `Room 9 - 60 Park Pl`)
- `smartrecruiters_location_id`
- `schoolmint_grow_location_id`
- `zendesk_organization_id` (verify Zendesk inbound field at engineer-side;
  rename column if different)

Engineer waits on Ops confirmation that sheet is populated and
`--target staging` external-table refresh is complete before starting Phase 2.

---

## Phase 1: Register new sheet source

### Task 1.1: Add `src_google_sheets__people__locations` to `sources-external.yml`

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (add new
  source entry alongside existing
  `src_google_sheets__people__location_crosswalk` at line ~1151)

- [ ] **Step 1: Add the new source entry**

Add after the `src_google_sheets__people__location_crosswalk` block (around line
1167):

```yaml
- name: src_google_sheets__people__locations
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/1FCc28XWxFj3gSfItGGJ2tVU0C1fYD1JxKRxuSFqisMo
      sheet_range: src_people__locations
      skip_leading_rows: 1
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - sheets
          - people
          - locations
```

- [ ] **Step 2: Parse**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-batch-c-locations-regions
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: parse succeeds; new source registered.

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/google/sheets/sources-external.yml
git commit -m "feat(dbt): register src_google_sheets__people__locations source"
```

---

## Phase 2: Rename and rewrite `stg_people__locations` → `stg_google_sheets__people__locations`

### Task 2.1: Create the new staging model

**Files:**

- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__people__locations.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml`
- Delete: `src/dbt/kipptaf/models/people/staging/stg_people__locations.sql`
- Delete:
  `src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml`

- [ ] **Step 1: Write the new staging SQL**

Create
`src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__people__locations.sql`:

```sql
with
    src as (
        select
            location_name,
            abbreviation,
            grade_band,
            powerschool_school_id,
            deanslist_school_id,
            reporting_school_id,
            is_campus,
            is_pathways,
            dagster_code_location,
            head_of_schools_employee_number,
            campus_name,
            address_line_one,
            address_line_two,
            city,
            postal_code,
            smartrecruiters_location_id,
            schoolmint_grow_location_id,
            zendesk_organization_id,
            region as business_unit,
            adp_location_code as adp_location_code_csv,
            case
                dagster_code_location
                when 'kippnewark'
                then 'Newark'
                when 'kippcamden'
                then 'Camden'
                when 'kippmiami'
                then 'Miami'
                when 'kipppaterson'
                then 'Paterson'
            end as region,
        from
            {{ source("google_sheets", "src_google_sheets__people__locations") }}
    ),

    unnested as (
        select
            s.* except (adp_location_code_csv),

            ifnull(
                trim(adp_code), s.adp_location_code_csv
            ) as adp_location_code,
        from src as s
        left join unnest(split(s.adp_location_code_csv, ',')) as adp_code
    )

select *
from unnested
```

- [ ] **Step 2: Write the properties YAML**

Create
`src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml`:

```yaml
models:
  - name: stg_google_sheets__people__locations
    description: |
      Canonical-grain people/location master. One row per (canonical
      location_name × adp_location_code) — multi-valued ADP codes are
      unnested so each ADP location string maps to exactly one canonical
      row. The Pathways/Whittier mart-scope filter applies in `dim_locations`,
      not here; staging carries all 38 canonical rows.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - location_name
              - adp_location_code
          config:
            severity: error
    columns:
      - name: location_name
        data_type: string
        description: Canonical location name. Single canonical spelling.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: abbreviation
        data_type: string
        description: Short location abbreviation (e.g., SPARK, NCA).
      - name: region
        data_type: string
        description: |
          Canonical region name derived from dagster_code_location
          (Newark, Camden, Miami, Paterson). Null for non-regional rows.
      - name: business_unit
        data_type: string
        description: |
          Legal-entity name the location rolls up to. Sourced from the
          sheet's `region` column (legal-entity values).
      - name: grade_band
        data_type: string
        description: Grade band served (e.g., ES, MS, HS).
      - name: powerschool_school_id
        data_type: int64
        description: PowerSchool school ID. Inbound FK input.
      - name: deanslist_school_id
        data_type: int64
        description: DeansList school ID. Inbound FK input.
      - name: reporting_school_id
        data_type: int64
        description: Reporting school ID for multi-campus rollup.
      - name: is_campus
        data_type: boolean
        description: True for physical-campus rows.
      - name: is_pathways
        data_type: boolean
        description: |
          True for KIPP Forward / Pathways post-secondary rows. Mart-scope
          filter in `dim_locations` excludes these.
      - name: dagster_code_location
        data_type: string
        description: |
          Dagster code location (kippnewark, kippcamden, kippmiami,
          kipppaterson). Used with powerschool_school_id for cross-region
          joins.
      - name: head_of_schools_employee_number
        data_type: string
        description: Employee number of the location's head of schools.
      - name: campus_name
        data_type: string
        description: |
          Parent campus name from the campus crosswalk (e.g.,
          "KIPP Miami - North Campus" rolls up multiple sibling schools).
      - name: address_line_one
        data_type: string
        description: |
          Physical street address line 1. Nullable for campus-rollup rows
          and locations without a physical street address.
      - name: address_line_two
        data_type: string
        description: Physical street address line 2. Nullable.
      - name: city
        data_type: string
        description: City. Nullable for non-physical rows.
      - name: postal_code
        data_type: string
        description: Postal code. Nullable for non-physical rows.
      - name: adp_location_code
        data_type: string
        description: |
          ADP work-location code. Multi-valued in the sheet
          (comma-separated); unnested at staging so each ADP code
          maps to exactly one canonical row.
      - name: smartrecruiters_location_id
        data_type: string
        description: SmartRecruiters location ID. Inbound FK input.
      - name: schoolmint_grow_location_id
        data_type: string
        description: SchoolMint Grow location ID. Inbound FK input.
      - name: zendesk_organization_id
        data_type: string
        description: |
          Zendesk organization ID (or whichever ticket-side field carries
          the location join key — confirm during implementation).
          Inbound FK input.
```

- [ ] **Step 3: Delete the old `stg_people__locations` files**

```bash
git rm src/dbt/kipptaf/models/people/staging/stg_people__locations.sql \
       src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml
```

- [ ] **Step 4: Parse**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: parse succeeds. Note: existing `ref("stg_people__locations")`
consumers will fail at compile in subsequent tasks — that's why those refs get
updated next.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__people__locations.sql \
        src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml
git commit -m "feat(dbt): add stg_google_sheets__people__locations canonical master"
```

### Task 2.2: Update `ref("stg_people__locations")` callers

**Files:** every `*.sql` containing `ref("stg_people__locations")` plus any
`.yml` describing its dependents.

- [ ] **Step 1: Find all callers**

```bash
grep -rln 'ref("stg_people__locations")' src/dbt --include="*.sql" --include="*.yml" | grep -v target
```

Expected files (verify against output):

- `src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- (any others surfaced by grep)

- [ ] **Step 2: Repoint each caller**

For each file: replace `ref("stg_people__locations")` with
`ref("stg_google_sheets__people__locations")`. Column references (e.g.
`loc.location_name`) stay identical — staging output preserves the canonical
column name.

- [ ] **Step 3: Parse and verify**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: parse succeeds.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor(dbt): repoint stg_people__locations → stg_google_sheets__people__locations"
```

---

## Phase 3: `dim_locations` and `dim_regions` mart additions

### Task 3.1: Move Pathways/Whittier filter into `dim_locations`; add address columns

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_locations.yml`

- [ ] **Step 1: Read current `dim_locations.sql` and
      `properties/dim_locations.yml`**

Confirm baseline column list and tests.

- [ ] **Step 2: Rewrite `dim_locations.sql`**

```sql
select
    {{ dbt_utils.generate_surrogate_key(["location_name"]) }} as location_key,

    if(
        region is not null,
        {{ dbt_utils.generate_surrogate_key(["region"]) }},
        cast(null as string)
    ) as region_key,

    location_name as `name`,
    grade_band,
    campus_name as campus,
    is_campus,
    address_line_one,
    address_line_two,
    city,
    postal_code,

    coalesce(abbreviation, location_name) as abbreviation,
from {{ ref("stg_google_sheets__people__locations") }}
where not is_pathways and location_name <> 'KIPP Whittier Elementary'
```

The `WHERE` clause is the migrated mart-scope filter (from
`stg_people__locations`).

- [ ] **Step 3: Update `properties/dim_locations.yml`**

Add four new columns (`address_line_one`, `address_line_two`, `city`,
`postal_code`) with `data_type: string` and descriptions matching the staging
YAML. Place under the existing `columns:` list after `abbreviation`.

```yaml
- name: address_line_one
  data_type: string
  description: Physical street address line 1. Nullable.
- name: address_line_two
  data_type: string
  description: Physical street address line 2. Nullable.
- name: city
  data_type: string
  description: City. Nullable for non-physical rows (e.g., campus rollups).
- name: postal_code
  data_type: string
  description: Postal code. Nullable for non-physical rows.
```

- [ ] **Step 4: Build and verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select dim_locations
```

Expected: 38 rows (matching today). PK uniqueness test passes. Note: the new
master sheet may produce a different row count if Ops added/removed rows during
bootstrap — investigate any deviation.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat(dbt): add address columns to dim_locations; move mart-scope filter from staging"
```

### Task 3.2: Add `business_unit_code` to `dim_regions`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_regions.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_regions.yml`

- [ ] **Step 1: Read current `dim_regions.sql` and properties**

The current model derives 5 region rows. We need to surface `business_unit_code`
(one of `KCNA`, `KIPP_MIAMI`, `KIPP_TAF`, `KPAT`, `TEAM`) — exact source is
whichever upstream model produces these rows. Inspect to determine.

- [ ] **Step 2: Add `business_unit_code` column to `dim_regions.sql`**

If the upstream already carries `business_unit_code` (likely via the People
canonical chain or `int_people__staff_roster`-related models), select it.
Otherwise add a hardcoded `case` mapping from existing region identity to the
canonical code. Coordinate with reviewers if uncertainty.

- [ ] **Step 3: Add `business_unit_code` column to
      `properties/dim_regions.yml`**

```yaml
- name: business_unit_code
  data_type: string
  description: |
    ADP business-unit code (KCNA, KIPP_MIAMI, KIPP_TAF, KPAT, TEAM). 1:1
    with regions. FK target for
    dim_work_assignment_organizational_units.business_unit_code.
  data_tests:
    - not_null
    - unique
```

Place at the top of the `columns:` list per the data-tests-first ordering
convention.

- [ ] **Step 4: Build and verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select dim_regions
```

Expected: 5 rows; uniqueness and not-null both pass.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat(dbt): add business_unit_code to dim_regions"
```

---

## Phase 4: Refactor `int_people__location_crosswalk`

### Task 4.1: Source canonical attrs from new master, preserve output schema

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__location_crosswalk.sql`

- [ ] **Step 1: Replace contents**

```sql
select
    lc.name as location_name,
    pl.location_name as location_clean_name,
    pl.abbreviation as location_abbreviation,
    pl.grade_band as location_grade_band,
    pl.region as location_region,
    pl.powerschool_school_id as location_powerschool_school_id,
    pl.deanslist_school_id as location_deanslist_school_id,
    pl.reporting_school_id as location_reporting_school_id,
    pl.is_campus as location_is_campus,
    pl.is_pathways as location_is_pathways,
    pl.dagster_code_location as location_dagster_code_location,
    pl.head_of_schools_employee_number
        as location_head_of_schools_employee_number,
    pl.campus_name,
from {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
inner join {{ ref("stg_google_sheets__people__locations") }} as pl
    on lc.clean_name = pl.location_name
```

The `inner join` collapses rows without a canonical match (which would be a data
error caught by the drift test in Phase 6).

- [ ] **Step 2: Build and verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_people__location_crosswalk
```

Expected: row count matches today's alias-grain count; uniqueness test passes;
column list unchanged.

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/people/intermediate/int_people__location_crosswalk.sql
git commit -m "refactor(dbt): int_people__location_crosswalk sources canonical attrs from master"
```

---

## Phase 5: Consumer repointing

For all SQL files currently
`ref("stg_google_sheets__people__location_crosswalk")` and reading canonical
attrs (not just `name`/`clean_name`), repoint to
`ref("int_people__location_crosswalk")` and update column references from
unprefixed to prefixed (`abbreviation` → `location_abbreviation`,
`powerschool_school_id` → `location_powerschool_school_id`, etc.).

**Mechanical pattern (apply per file):**

1. Find `{{ ref("stg_google_sheets__people__location_crosswalk") }} as <alias>`
   → replace with `{{ ref("int_people__location_crosswalk") }} as <alias>`.
2. Update join condition if it joined on
   `<alias>.name = <upstream>.<alias_name_string>` → keep as
   `<alias>.location_name = <upstream>.<alias_name_string>` (the alias column on
   the int model is named `location_name`).
3. Update join condition if it joined on `<alias>.clean_name = ...` → use
   `<alias>.location_clean_name`.
4. Update every projected column from `<alias>.<col>` to
   `<alias>.location_<col>` for each canonical-attr column. (Skip `<alias>.name`
   which becomes `<alias>.location_name`; skip `<alias>.clean_name` which
   becomes `<alias>.location_clean_name`.)
5. If the file references `<alias>.location_dagster_code_location` it's already
   prefixed — no change.
6. `cc.name` (if joined to campus crosswalk) — campus_name is now
   `<alias>.campus_name` on int, no separate join needed.

### Task 5.1: Repoint Amplify mClass intermediates

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__benchmark_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__pm_student_summary.sql`

- [ ] **Step 1: Apply mechanical pattern to both files**

Existing pattern (sketch from
`int_amplify__mclass__benchmark_student_summary.sql:17-28`):

```sql
location_xref as (
    select
        x.abbreviation as school,
        x.powerschool_school_id as schoolid,
        ...
    from {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
    on ur.school_name = x.name
)
```

Becomes:

```sql
location_xref as (
    select
        x.location_abbreviation as school,
        x.location_powerschool_school_id as schoolid,
        ...
    from {{ ref("int_people__location_crosswalk") }} as x
    on ur.school_name = x.location_name
)
```

- [ ] **Step 2: Build downstream to verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select int_amplify__mclass__benchmark_student_summary+ \
           int_amplify__mclass__pm_student_summary+
```

Expected: builds clean.

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/amplify/
git commit -m "refactor(dbt): repoint amplify mclass intermediates to int_people__location_crosswalk"
```

### Task 5.2: Repoint iReady intermediates

**Files:**

- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__diagnostic_results.sql`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__instruction_by_lesson.sql`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__instruction_by_lesson_pro.sql`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__instructional_usage_data.sql`

- [ ] **Step 1: Apply mechanical pattern**

For each file, change `ref("stg_google_sheets__people__location_crosswalk")` →
`ref("int_people__location_crosswalk")` and prefix column refs (`abbreviation` →
`location_abbreviation`, etc.). Confirm `extract_code_location()` matching
against `dagster_code_location` becomes `location_dagster_code_location`.

- [ ] **Step 2: Build downstream**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select int_iready__diagnostic_results+ \
           int_iready__instruction_by_lesson+ \
           int_iready__instruction_by_lesson_pro+ \
           int_iready__instructional_usage_data+
```

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/iready/
git commit -m "refactor(dbt): repoint iready intermediates to int_people__location_crosswalk"
```

### Task 5.3: Repoint remaining intermediates

**Files:**

- Modify:
  `src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__observations.sql`
- Modify:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__status_report_unpivot.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_interventions.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__referral_suspension_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__temp_staff.sql`

- [ ] **Step 1: Apply mechanical pattern to each file**

- [ ] **Step 2: Build downstream**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select int_performance_management__observations+ \
           int_finalsite__status_report_unpivot+ \
           int_students__attendance_interventions+ \
           int_extracts__student_enrollments+ \
           int_deanslist__referral_suspension_rollup+ \
           int_people__temp_staff+
```

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "refactor(dbt): repoint remaining intermediates to int_people__location_crosswalk"
```

### Task 5.4: Repoint `stg_powerschool__storedgrades`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql`

- [ ] **Step 1: Apply mechanical pattern**

The current join (`stg_powerschool__storedgrades.sql:36-39`):

```sql
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as l
    on u.schoolname = l.name
```

Becomes:

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as l
    on u.schoolname = l.location_name
```

The downstream `is_transfer_grade = if(l.name is null, true, false)` →
`is_transfer_grade = if(l.location_name is null, true, false)`.

- [ ] **Step 2: Build downstream**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select stg_powerschool__storedgrades+
```

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql
git commit -m "refactor(dbt): repoint stg_powerschool__storedgrades to int_people__location_crosswalk"
```

### Task 5.5: Repoint reporting/extracts (`rpt_*`)

**Files** (verify list with
`grep -rln 'ref("stg_google_sheets__people__location_crosswalk")' src/dbt/kipptaf/models/extracts/`):

- `src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql`
- `src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql`
- `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__iready_lessons.sql`
- `src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__seat_tracker_roster.sql`
- `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__njdoe_universal_screener_data.sql`
- `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__pm_assignment_roster.sql`
- `src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_behavior.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_referrals.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__operations_ekg.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__operations_pm.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__powerschool_calendar_day.sql`

- [ ] **Step 1: Apply mechanical pattern to each**

Same as prior repoint tasks: `ref()` swap + column-name prefix update.

- [ ] **Step 2: Parse and build**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select extracts/
```

Expected: parse succeeds; extracts build clean.

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/extracts/
git commit -m "refactor(dbt): repoint extract/reporting models to int_people__location_crosswalk"
```

### Task 5.6: Verify no remaining references to alias-staging columns

- [ ] **Step 1: Grep**

```bash
grep -rn 'ref("stg_google_sheets__people__location_crosswalk")' src/dbt/kipptaf/models --include="*.sql" | grep -v target
```

Expected: only `int_people__location_crosswalk.sql` itself (and possibly
`stg_people__locations.sql` if not yet deleted in Phase 2 — should be deleted by
now).

- [ ] **Step 2: Repeat for properties YAML**

```bash
grep -rn "stg_google_sheets__people__location_crosswalk" src/dbt/kipptaf/models --include="*.yml" | grep -v target
```

Verify no leftover references from the old prefix-less columns.

---

## Phase 6: Alias-sheet trim (off-PR Ops, plus source YAML update)

### Task 6.1: Update source YAML to reflect trimmed sheet schema

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (the
  `src_google_sheets__people__location_crosswalk` block — trim the `columns:`
  list if present)
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__people__location_crosswalk.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__location_crosswalk.yml`

**Coordinate with Ops**: Ops removes the duplicated canonical-attr columns from
the `src_people__location_crosswalk` sheet tab BEFORE this task lands. Engineer
waits for confirmation.

- [ ] **Step 1: Rewrite `stg_google_sheets__people__location_crosswalk.sql` to
      expose 2 columns only**

```sql
select
    name,
    clean_name,
from {{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }}
```

- [ ] **Step 2: Update
      `properties/stg_google_sheets__people__location_crosswalk.yml`**

Strip canonical-attr columns; retain `name` (alias) and `clean_name`
(canonical). Update the description to clarify the alias-grain role:

```yaml
models:
  - name: stg_google_sheets__people__location_crosswalk
    description: |
      Alias-grain crosswalk: maps alternate location names to canonical
      names. Canonical attributes (abbreviation, region, IDs) are no
      longer carried here — see int_people__location_crosswalk for the
      full alias × canonical-attr surface.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - name
              - clean_name
          config:
            severity: error
    columns:
      - name: name
        data_type: string
        description: Alternate-spelling alias of a canonical location.
      - name: clean_name
        data_type: string
        description: |
          Canonical location name. Join key to
          stg_google_sheets__people__locations.location_name.
        data_tests:
          - not_null:
              config:
                severity: error
```

- [ ] **Step 3: Add custom drift test**

Append to `properties/stg_google_sheets__people__location_crosswalk.yml` a test
verifying every distinct `clean_name` exists as `location_name` in the new
master, and vice versa. Use a `dbt_utils.relationships` test on
`clean_name → stg_google_sheets__people__locations.location_name`. For the
reverse direction, add the test on the master:

In `stg_google_sheets__people__locations.yml`, add an `equality`-style test (use
`dbt_utils.equality` if available, otherwise a custom singular test). Sketch:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns: ... # already present
  - dbt_utils.relationships: # new
      arguments:
        column_name: location_name
        to: ref('stg_google_sheets__people__location_crosswalk')
        field: clean_name
      config:
        severity: error
```

(In `stg_google_sheets__people__location_crosswalk.yml`:)

```yaml
columns:
  - name: clean_name
    data_tests:
      - not_null:
          config:
            severity: error
      - relationships:
          arguments:
            to: ref('stg_google_sheets__people__locations')
            field: location_name
          config:
            severity: error
```

- [ ] **Step 4: Build to verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select stg_google_sheets__people__location_crosswalk \
           stg_google_sheets__people__locations
```

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__people__location_crosswalk.sql \
            src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__location_crosswalk.yml \
            src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml
git commit -m "refactor(dbt): trim stg_google_sheets__people__location_crosswalk to alias grain"
```

---

## Phase 7: Source-system enrichment

For each source system, attach `location_key` resolved via the canonical master
at the highest shared pivot point.

### Task 7.1: PowerSchool — wrap union in CTE on `stg_powerschool__schools`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__schools.yml`

- [ ] **Step 1: Rewrite `stg_powerschool__schools.sql`**

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__schools"),
                    source("kippcamden_powerschool", "stg_powerschool__schools"),
                    source("kippmiami_powerschool", "stg_powerschool__schools"),
                    source("kipppaterson_powerschool", "stg_powerschool__schools"),
                ]
            )
        }}
    )

select
    u.*,

    if(
        loc.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }},
        cast(null as string)
    ) as location_key,
from unioned as u
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_number = loc.powerschool_school_id
```

- [ ] **Step 2: Update properties YAML**

Add `location_key` column at top of the columns list:

```yaml
- name: location_key
  data_type: string
  description: |
    Canonical location_key resolved via the people canonical master on
    powerschool_school_id. NULL for the `999999` "Graduated Students"
    sentinel and any unmapped school.
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_locations')
          field: location_key
        config:
          severity: error
```

Also update the model-level uniqueness test if needed (current grain may need a
recheck after the join).

- [ ] **Step 3: Build and verify**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select stg_powerschool__schools
```

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql \
            src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__schools.yml
git commit -m "feat(dbt): attach location_key to stg_powerschool__schools via canonical master"
```

### Task 7.2: ADP — attach `location_key` in `int_adp_workforce_now__workers__work_assignments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/int_adp_workforce_now__workers__work_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/properties/int_adp_workforce_now__workers__work_assignments.yml`

- [ ] **Step 1: Read current file**

Identify the final `SELECT` and the row-grain key column (`item_id`).

- [ ] **Step 2: Add `location_key` resolution**

In the model's final `SELECT`, add:

```sql
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on wa.home_work_location__name_code__code_value
       = loc.adp_location_code
```

Then in the `SELECT` list:

```sql
if(
    loc.location_name is not null,
    {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }},
    cast(null as string)
) as location_key,
```

- [ ] **Step 3: Update properties YAML**

Add `location_key` column with relationships test to
`dim_locations.location_key`.

- [ ] **Step 4: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_adp_workforce_now__workers__work_assignments
```

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/int_adp_workforce_now__workers__work_assignments.sql \
            src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/properties/int_adp_workforce_now__workers__work_assignments.yml
git commit -m "feat(dbt): attach location_key to int_adp_workforce_now__workers__work_assignments"
```

### Task 7.3: DeansList — wrap union in CTE on `int_deanslist__incidents`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__incidents.yml`

- [ ] **Step 1: Rewrite `int_deanslist__incidents.sql`**

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    )

select
    u.*,

    if(
        loc.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }},
        cast(null as string)
    ) as location_key,
from unioned as u
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
```

- [ ] **Step 2: Update properties YAML**

Add `location_key` column with relationships test.

- [ ] **Step 3: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_deanslist__incidents
```

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql \
            src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__incidents.yml
git commit -m "feat(dbt): attach location_key to int_deanslist__incidents via canonical master"
```

### Task 7.4: Zendesk — attach `location_key` in `int_zendesk__tickets__custom_fields_pivot`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/zendesk/intermediate/int_zendesk__tickets__custom_fields_pivot.sql`
- Modify:
  `src/dbt/kipptaf/models/zendesk/intermediate/properties/int_zendesk__tickets__custom_fields_pivot.yml`

- [ ] **Step 1: Identify the Zendesk inbound location field**

Read the model's existing custom-fields columns to identify which carries the
canonical location identifier (likely an organization-id-like field or a custom
field exposing `zendesk_organization_id`). Confirm with Ops/spec authors that
the field on the master (`zendesk_organization_id`) matches what tickets carry.

- [ ] **Step 2: Add the join and `location_key` projection**

```sql
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on cf.<zendesk_inbound_field> = loc.zendesk_organization_id
```

Then add the `location_key` projection with the nullable surrogate-key wrap
pattern.

- [ ] **Step 3: Update properties YAML**

- [ ] **Step 4: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_zendesk__tickets__custom_fields_pivot
```

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/kipptaf/models/zendesk/intermediate/int_zendesk__tickets__custom_fields_pivot.sql \
            src/dbt/kipptaf/models/zendesk/intermediate/properties/int_zendesk__tickets__custom_fields_pivot.yml
git commit -m "feat(dbt): attach location_key to int_zendesk__tickets__custom_fields_pivot"
```

### Task 7.5: Seat Tracker — attach `location_key` in `int_seat_tracker__snapshot`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/appsheet/intermediate/int_seat_tracker__snapshot.sql`
- Modify:
  `src/dbt/kipptaf/models/google/appsheet/intermediate/properties/int_seat_tracker__snapshot.yml`

- [ ] **Step 1: Add `location_key` resolution**

The model's `adp_location` column holds typed strings (e.g.
`Room 9 - 60 Park Pl`). The new master's `adp_location_code` (post-unnest) is
one row per ADP code. Join on `adp_location = adp_location_code`:

```sql
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on s.adp_location = loc.adp_location_code
```

Then add the nullable surrogate-key projection.

- [ ] **Step 2: Update properties YAML**

- [ ] **Step 3: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_seat_tracker__snapshot
```

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/kipptaf/models/google/appsheet/intermediate/int_seat_tracker__snapshot.sql \
            src/dbt/kipptaf/models/google/appsheet/intermediate/properties/int_seat_tracker__snapshot.yml
git commit -m "feat(dbt): attach location_key to int_seat_tracker__snapshot"
```

### Task 7.6: SchoolMint Grow — attach `location_key` in `int_schoolmint_grow__observations`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml`

- [ ] **Step 1: Identify SchoolMint Grow location field**

Read the model — find which column carries the SchoolMint Grow location
identifier (likely `school_id` or similar). Confirm with the master's
`schoolmint_grow_location_id` column.

- [ ] **Step 2: Add the join and `location_key` projection**

```sql
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on o.<schoolmint_grow_location_field> = loc.schoolmint_grow_location_id
```

Plus the nullable surrogate-key wrap.

- [ ] **Step 3: Update properties YAML**

- [ ] **Step 4: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select int_schoolmint_grow__observations
```

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql \
            src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml
git commit -m "feat(dbt): attach location_key to int_schoolmint_grow__observations"
```

---

## Phase 8: Mart child fixes

### Task 8.1: #3720 mart child models — repoint `location_key` source

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_support_tickets.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_course_sections.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql`
- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_job_candidate_applications.sql`

Each consumes `location_key` from its source-system pivot (no master join in the
mart) — except SmartRecruiters which joins the master directly.

- [ ] **Step 1: `fct_support_tickets` — read `location_key` from
      `int_zendesk__tickets__custom_fields_pivot`**

Replace any direct master/crosswalk join with a `select cf.location_key` from
the existing Zendesk join.

- [ ] **Step 2: `dim_student_enrollments` and `dim_course_sections` — read
      `location_key` from `stg_powerschool__schools`**

Replace the existing `stg_google_sheets__people__locations` join (or whatever
the current resolution path is) with a join to `stg_powerschool__schools`,
projecting its `location_key` column directly. The PowerSchool sentinel handling
is already done in the schools staging via the LEFT JOIN.

- [ ] **Step 3: `dim_staffing_positions` — read `location_key` from
      `int_seat_tracker__snapshot`**

Replace the inline `generate_surrogate_key(["adp_location"])` call (currently in
`dim_staffing_positions.sql:5-8`) with a join projecting `s.location_key` from
`int_seat_tracker__snapshot`.

- [ ] **Step 4: `fct_staff_observations` — read `location_key` from
      `int_schoolmint_grow__observations`**

Replace the existing `int_people__location_crosswalk` join (which today resolves
on alias name) with a direct read of `location_key` from
`int_schoolmint_grow__observations`. Drop the alias-name lookup if no longer
needed for other columns.

- [ ] **Step 5: `fct_job_candidate_applications` — direct master join**

Add (or update) a join to `stg_google_sheets__people__locations` on whatever
SmartRecruiters location-id column is on the model:

```sql
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on app.<smartrecruiters_location_id_field> = loc.smartrecruiters_location_id
```

Replace `shared_with_location_key` with the nullable surrogate-key wrap pattern
producing the FK.

- [ ] **Step 6: Update each mart's properties YAML**

Each mart's `properties/<model>.yml` should keep its existing `location_key` (or
`shared_with_location_key`) column with relationships test to `dim_locations`.
No type/contract change.

- [ ] **Step 7: Build all six**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select fct_support_tickets dim_student_enrollments dim_course_sections \
           dim_staffing_positions fct_staff_observations fct_job_candidate_applications
```

Expected: each builds clean; existing relationships tests now PASS (~309K
orphans resolved).

- [ ] **Step 8: Commit**

```bash
git add -u src/dbt/kipptaf/models/marts/
git commit -m "fix(dbt): #3720 child marts read location_key from source-system pivots"
```

### Task 8.2: PowerSchool consistency migration — flip 5 marts to use `stg_powerschool__schools`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_goals.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_targets.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql`
- Modify: `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`

- [ ] **Step 1: For each, repoint `location_key` resolution to
      `stg_powerschool__schools.location_key`**

Each model currently resolves `location_key` via some path that ends up matching
today's surrogate values. Switch the path: join `stg_powerschool__schools` and
read its `location_key` column directly.

- [ ] **Step 2: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging \
  --select dim_assessment_goals dim_assessment_targets dim_school_calendars \
           dim_terms fct_student_attendance_daily
```

Expected: each builds clean; `location_key` values identical to today (no row
count or value change).

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/kipptaf/models/marts/
git commit -m "refactor(dbt): PowerSchool marts read location_key from stg_powerschool__schools"
```

### Task 8.3: DeansList R9 on `fct_behavioral_incidents`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml`

- [ ] **Step 1: Add `location_key` from `int_deanslist__incidents` and drop
      degenerate `location` string**

In `fct_behavioral_incidents.sql`:

- Replace any selection of `i.location` (degenerate string) with selection of
  `i.location_key` from the upstream `int_deanslist__incidents`.
- Drop `i.location` from the SELECT list.

- [ ] **Step 2: Update properties YAML**

- Remove the `location` column entry.
- Add `location_key`:

```yaml
- name: location_key
  data_type: string
  description: |
    Canonical location_key resolved via int_deanslist__incidents on
    DeansList school_id. Nullable for unmapped school_ids.
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_locations')
          field: location_key
        config:
          severity: error
```

Place at top of columns list per data-tests-first ordering.

- [ ] **Step 3: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select fct_behavioral_incidents
```

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql \
            src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml
git commit -m "fix(dbt): R9 fct_behavioral_incidents.location → location_key FK"
```

### Task 8.4: ADP `dim_work_assignment_locations` — `location_key` FK + R9 + boundary normalization

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_locations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_locations.yml`

- [ ] **Step 1: Rewrite `dim_work_assignment_locations.sql`**

```sql
with
    assignments as (
        select
            wa.item_id,
            wa.effective_date_start,
            wa.location_key,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
    ),

    change_detection as (
        select
            *,

            lag(location_key, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as location_key_lag,
        from assignments
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            location_key,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where coalesce(location_key, '') != coalesce(location_key_lag, '')
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_location_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    location_key,
    effective_date_start as effective_start_date,
    effective_date_end as effective_end_date,

    if(effective_date_end = '9999-12-31', true, false) as is_current,
from change_points
```

Notes on the rewrite:

- `attribute_hash` is gone; `location_key` itself drives boundary detection
  (this is the SCD2 boundary normalization).
- The 8 denormalized address columns are dropped (R9).
- Because `location_key` is nullable, the change-detection comparison wraps in
  `coalesce(..., '')` so two consecutive NULL versions don't double-trigger.

- [ ] **Step 2: Update properties YAML**

Remove the dropped column entries. Add `location_key` with relationships test.
Keep `work_assignment_location_key` (PK) and `work_assignment_key` (parent FK).

```yaml
- name: location_key
  data_type: string
  description: |
    Canonical location_key resolved upstream in
    int_adp_workforce_now__workers__work_assignments via the canonical
    master on adp_location_code.
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_locations')
          field: location_key
        config:
          severity: error
```

- [ ] **Step 3: Pre/post row-count check (record in PR description)**

Before building, capture the current row count:

```sql
SELECT COUNT(*) FROM `kipptaf_marts.dim_work_assignment_locations`
```

Build, then capture the post-build count from the staging schema:

```sql
SELECT COUNT(*) FROM `dbt_cloud_pr_<ci_id>_<pr_num>_marts.dim_work_assignment_locations`
```

The post count must be ≤ pre count (collapse may reduce). Record both numbers in
the PR description.

- [ ] **Step 4: Pre-merge orphan-FK check**

Identify any mart FKing to `work_assignment_location_key`:

```bash
grep -rln "work_assignment_location_key" src/dbt/kipptaf/models --include="*.sql" | grep -v target
```

For each downstream consumer, verify the consumer's FK set is a subset of
post-collapse keys:

```sql
SELECT COUNT(*) FROM <consumer>
WHERE work_assignment_location_key NOT IN (
    SELECT work_assignment_location_key FROM dim_work_assignment_locations
)
```

Expected: 0. Record finding in PR description.

- [ ] **Step 5: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select dim_work_assignment_locations
```

- [ ] **Step 6: Commit**

```bash
git add -u src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_locations.sql \
            src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_locations.yml
git commit -m "feat(dbt): dim_work_assignment_locations FK + R9 + SCD2 boundary normalization"
```

### Task 8.5: `business_unit_code` FK from `dim_work_assignment_organizational_units`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_organizational_units.sql`
  (if needed — column may already be exposed)
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_organizational_units.yml`

- [ ] **Step 1: Confirm `business_unit_code` is already on the model**

It should be (per spec). If not, add it from the upstream ADP source.

- [ ] **Step 2: Add relationships test**

In properties YAML, on `business_unit_code`:

```yaml
- name: business_unit_code
  data_type: string
  description: |
    ADP business-unit code. FK to dim_regions.business_unit_code.
  data_tests:
    - not_null
    - relationships:
        arguments:
          to: ref('dim_regions')
          field: business_unit_code
        config:
          severity: error
```

- [ ] **Step 3: Build**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging --select dim_work_assignment_organizational_units
```

Expected: relationships test passes (5 distinct codes match `dim_regions`).

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_organizational_units.sql \
            src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_organizational_units.yml
git commit -m "feat(dbt): dim_work_assignment_organizational_units.business_unit_code FK to dim_regions"
```

---

## Phase 9: Verification, lint, and audit-spec entry

### Task 9.1: Full project build

- [ ] **Step 1: Full parse**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: clean.

- [ ] **Step 2: Full build (staging target)**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target staging
```

Expected: every model builds; the six previously-failing #3720 relationships
tests now pass; new tests pass; SCD2 row count check satisfied.

### Task 9.2: Add audit-spec hash-change entry

**Files:**

- Modify: `docs/superpowers/specs/2026-04-15-column-naming-audit.md` — append to
  the "Enumerated surrogate-key changes" table.

- [ ] **Step 1: Add entries**

| Model                            | Column                     | Rule | Reason                                                          |
| -------------------------------- | -------------------------- | ---- | --------------------------------------------------------------- |
| `dim_work_assignment_locations`  | `location_key`             | 5    | Structural add — new FK column                                  |
| `dim_student_enrollments`        | `location_key`             | 4    | Null handling change — sentinel `999999` now NULL via LEFT JOIN |
| `dim_course_sections`            | `location_key`             | 4    | Same as above                                                   |
| `fct_behavioral_incidents`       | `location_key`             | 5    | Structural add — replaces degenerate `location` string          |
| `fct_support_tickets`            | `location_key`             | 1    | Values unify — resolution path through Zendesk pivot            |
| `dim_staffing_positions`         | `location_key`             | 1    | Values unify — resolution path through Seat Tracker pivot       |
| `fct_staff_observations`         | `location_key`             | 1    | Values unify — resolution path through SchoolMint Grow pivot    |
| `fct_job_candidate_applications` | `shared_with_location_key` | 1    | Values unify — direct master join                               |

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-15-column-naming-audit.md
git commit -m "docs(audit): record Batch C surrogate-key changes"
```

### Task 9.3: Trunk lint

- [ ] **Step 1: Run trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
```

Expected: pass. Fix any sqlfluff issues inline (single-quote string literals,
line ≤88, trailing commas, no `select *` in mart finals — see
`src/dbt/CLAUDE.md` for the full rule list).

- [ ] **Step 2: Commit any lint fixes**

```bash
git add -u
git commit -m "style(dbt): trunk lint fixes"
```

### Task 9.4: Push and open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin cbini/refactor/claude-batch-c-locations-regions
```

- [ ] **Step 2: Open PR**

Use `.github/pull_request_template.md` as the body. Title:
`refactor(dbt): batch C — locations & regions`.

PR body must include:

- Closes #3720, #3689, #3690.
- Reference to spec:
  `docs/superpowers/specs/2026-04-27-batch-c-locations-regions-design.md`.
- Pre/post SCD2 row count for `dim_work_assignment_locations` (from Task 8.4
  step 3).
- Pre-merge orphan-FK check result (from Task 8.4 step 4).
- Confirmation that the new master sheet has been bootstrapped by Ops and the
  alias sheet trim has been completed.

- [ ] **Step 3: Verify dbt Cloud CI run**

```bash
gh pr checks
```

Expected: dbt Cloud CI job passes
(`dbt build --select state:modified+ --full-refresh`, target `staging`).

---

## Self-review checklist

After implementation completes:

- [ ] Every consumer of `stg_google_sheets__people__location_crosswalk` (per the
      consumer survey in the spec) is now reading from
      `int_people__location_crosswalk` or has been documented as not requiring
      repoint.
- [ ] No remaining references to dropped columns on
      `dim_work_assignment_locations` (the 8 denormalized address cols).
- [ ] `fct_behavioral_incidents.location` (the degenerate string) is gone;
      `location_key` is a tested FK.
- [ ] `dim_regions.business_unit_code` is unique, not-null, and FK'd from
      `dim_work_assignment_organizational_units`.
- [ ] All 38 canonical rows in `dim_locations` have address fields populated (or
      knowingly nullable for campus rollups).
- [ ] PR description records pre/post SCD2 row counts and orphan-FK check
      results.
