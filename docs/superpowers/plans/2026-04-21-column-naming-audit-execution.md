# Column-Naming Audit Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved column-naming decisions to every mart model
(dimensions, facts, bridges) so analyst-facing columns follow one rubric, with
upstream prerequisite fixes that unblock the R9 FK traversals.

**Architecture:** Three phases executed as a single PR on branch
`cbini/feat/claude-column-naming-audit`. Phase 1 fixes upstream blockers so R9
removes + structural FK adds work downstream. Phase 2 applies per-domain mart
changes from the authoritative inventory CSV. Phase 3 sweeps exposures,
documents hash-change impact, and opens the PR.

**Tech Stack:** dbt 1.11 on BigQuery, `dbt_utils`, Python (for inventory
filtering via `pandas`), no new code dependencies.

**Authoritative sources:**

- Decisions (168 renames, 180 removes, 25 adds, 520 keeps across 67 mart
  models):
  [docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv](../specs/2026-04-15-column-naming-audit-inventory.csv)
- Rubric + rationale:
  [docs/superpowers/specs/2026-04-15-column-naming-audit.md](../specs/2026-04-15-column-naming-audit.md)

**Workspace:** Worktree at
`/workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit`. All
`git` and `uv run` commands execute from the worktree (the main repo and
worktree have separate HEADs).

---

## File structure

Every touched file is listed below. New code files are rare — this is mostly
edits to existing mart SQL + their properties YAML.

### Created

- `src/dbt/kipptaf/models/people/staging/stg_people__locations.sql` — new
  canonical-grain locations staging model (1 row per logical school).
- `src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml` —
  YAML contract for the above.

### Modified — upstream prerequisites (Phase 1)

- `src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql` — dead-weight row
  filter.
- `src/dbt/kipptaf/models/people/staging/stg_people__locations.sql` — `region`
  column renamed to `business_unit`; new canonical `region` derived from
  `dagster_code_location`.
- `src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml` —
  matching rename + add.
- 7 canonical-seeking consumers rerouted from `int_people__location_crosswalk`
  to `stg_people__locations`.

### Modified — mart SQL + YAML (Phase 2)

67 mart models across 14 domains in
`src/dbt/kipptaf/models/marts/{dimensions,facts,bridges}/` and their
`properties/` YAML siblings. See per-domain tasks for full model lists.

### Modified — exposures (Phase 3)

- `src/dbt/kipptaf/models/exposures/**/*.yml` — any exposure referencing a
  renamed mart column.

### Modified — spec + plan (Phase 3)

- `docs/superpowers/specs/2026-04-15-column-naming-audit.md` — enumerated
  surrogate keys whose hash changed and why.

---

## Procedure — per-model change pattern

Every Phase 2 task applies this pattern once per model in the domain. Reference
this section; do not repeat it in per-task step lists.

### Inputs

- Mart SQL:
  `src/dbt/kipptaf/models/marts/{dimensions,facts,bridges}/<model>.sql`
- Mart YAML: adjacent `properties/<model>.yml`
- Inventory rows filtered by model:

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit
  uv run --with pandas python <<'PY'
  import pandas as pd
  df = pd.read_csv(
      'docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv',
      keep_default_na=False, na_values=[''],
  )
  u = df[df['model'] == '<model_name>']
  print(u[['current_column','action','proposed_name','rule_ref','reviewer_notes']].to_string(max_colwidth=200))
  PY
  ```

### Actions, per inventory `action` column

#### `rename`

SQL: change the column alias at the final `SELECT`. Do **not** rename the
upstream source column — the rename is mart-layer only unless the
`reviewer_notes` explicitly calls for an upstream rename.

```sql
-- Before
select
    old_name,
-- After
select
    old_name as new_name,
```

YAML: update `name:`. Preserve `data_tests:` and `config.meta` blocks on the
renamed column (migrate them intact). Update the `description:` only when the
current YAML description is clearly stale (e.g., still names the old column,
references a removed sibling, or was copy-pasted from an unrelated upstream
model). When the rename is followed by a type coercion (see below), adjust
`data_type:` to match the new output type and refresh the description to reflect
the new semantics.

#### `remove`

SQL: strip the column from the final `SELECT`. If the removed column was derived
in a CTE whose only surviving consumers also dropped it, remove the derivation
too.

YAML: delete the column block entirely.

If the removed column carried a `data_tests:` entry (e.g., `unique` on a natural
key being removed), verify the replacement key (usually the surrogate `*_key`)
already carries the equivalent test. If not, add it on the replacement.

#### `add`

SQL: add the new column to the final `SELECT`.

For FK adds, derive via `dbt_utils.generate_surrogate_key` wrapped with the
nullable-wrap helper when the source key can be null:

```sql
if(
    source_column is not null,
    {{ dbt_utils.generate_surrogate_key(["source_column"]) }},
    cast(null as string)
) as fk_column,
```

The hash **must** match the parent dim's `*_key` derivation. If the parent
hashes a different field (e.g. a join-resolved name rather than the raw source
key on this model), derive the FK via a lookup in a CTE so the input matches.

YAML: add the column block with:

- `data_type:` matching the SQL output.
- `description:` qualitative, analyst-facing (no stats; describe meaning, not
  distribution).
- FK adds: `relationships` test pointing to the parent dim's `*_key`. Include
  `not_null` only when the source is guaranteed non-null; otherwise rely on
  nullable-wrap + `relationships`.

#### Coverage-gap exception — `severity: warn` + TODO issue

When an FK derivation is correct but upstream data coverage is incomplete (some
source values don't resolve in the parent dim), downgrade the `relationships`
test severity and reference a tracked issue:

```yaml
data_tests:
  # TODO: #<issue> — <match %> rows fail FK; promote to error once crosswalk
  # covers the unresolved values.
  - relationships:
      arguments:
        to: ref('<parent_dim>')
        field: <parent_key>
      config:
        severity: warn
```

Open the issue first (`gh issue create`), capture its number, then write the
TODO. Issues created during this PR:

- [#3672](https://github.com/TEAMSchools/teamster/issues/3672) —
  `fct_job_candidate_applications.shared_with_location_key` ~20% FK miss.

### Per-model verification (required)

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit
uv run dbt compile --project-dir src/dbt/kipptaf --select <model_name>
```

Expected: exit 0, SQL emitted without warnings. `dbt compile` parses the full
project first — a separate `dbt parse` call is redundant.

### Per-domain commit

One commit per Phase 2 domain task, covering all models in the domain.
Conventional-commits form with the domain name:

```text
refactor(dbt): rename mart columns - <Domain> domain per #3643
```

Stage files explicitly (`git add <paths>`, never `-u`/`-A`/`.`). Do not use
`--no-verify`. If the pre-commit hook reformats files via trunk, it modifies
them in place and the commit succeeds.

---

## Rubric recap (spec lines 35–98)

Numbering used in inventory `rule_ref` column:

| Rule | Summary                                                                                                                                                                                           |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1   | Strip source-system prefixes/jargon (`powerschool_`, `adp_`, etc.) unless disambiguating.                                                                                                         |
| R2   | No KIPP-specific language (`teammate`, `employee_number`, `microgoal`, `commlog`).                                                                                                                |
| R3   | `is_`/`has_` prefix for booleans. Fact-table countable 0/1 flags may use INT64 so `SUM`/`AVG` work without casting; `FLOAT64` reserved for genuinely non-binary weights (e.g., `present_weight`). |
| R4   | Dates end `_date`; timestamps end `_timestamp`. Strict suffix convention.                                                                                                                         |
| R5   | Well-known external acronyms allowed for specific-use IDs.                                                                                                                                        |
| R6   | Ed-Fi Unified Data Model nomenclature is the default; deviate toward plain English for awkward descriptive attributes.                                                                            |
| R7   | Keep ubiquitous acronyms (`gpa`, `ada`, `fte`, `dob`, `ell`, `iep`, `sat`, `psat`, `act`, `ap`, `lea`, `nces`, `fleid`, `smid`); spell out internal ones.                                         |
| R8   | Plumbing columns removed from mart SELECTs (remain in staging/intermediate).                                                                                                                      |
| R9   | Remove dimension attributes reachable via FK traversal (denormalized copies).                                                                                                                     |

`structural` (new column add) and `exception` (specific-use jargon allowed) are
non-rubric tags used in the inventory.

---

## Group 3 — structural deferrals (out of scope this PR)

The inventory includes structural adds that require upstream work beyond this
PR's scope. Leave these unapplied; tracked in
[#3631](https://github.com/TEAMSchools/teamster/issues/3631):

1. **`fct_grades_assignments` score split** — adds `points_earned` +
   `numeric_grade_earned`; removes `score` + `score_type`. Requires staging
   changes to compute the split from the upstream score field.
2. **`dim_locations` address unification** — adds `address_line_one`,
   `address_line_two`, `city`, `postal_code`. Prerequisite for the work-location
   FK below.
3. **`dim_work_assignment_locations` FK to `dim_locations`** — removes 8 ADP
   address columns, adds `location_key`. Blocked by (2) and by a reliable
   mapping from ADP `home_work_location__name_code__code_value` to
   `dim_locations.location_name`.
4. **Business-unit / region FK parity** — optional: add `business_unit_code` to
   `dim_regions` so staff-side business_unit can FK directly. Requires alignment
   on canonical business-unit code values.

These four items together enable the
`dim_staff → dim_staff_work_assignments → dim_work_assignment_locations → dim_locations → dim_regions`
chain, currently left as attribute-only via `business_unit_name` string.

For each deferral, the inventory has `add` / `remove` rows that this plan
explicitly skips — see per-domain task notes.

---

## Phase 1 — Upstream prerequisites

Two independent fixes that unblock downstream R9 removes and FK adds. One commit
each.

### Task 1: Filter dead-weight rows in `dim_staff` (#3637)

**Background:** `stg_people__employee_numbers` accumulates NULL-keyed duplicate
rows because its incremental MERGE never matches on NULL merge keys. 91
`employee_number` values with `NULL adp_associate_id` accumulate 16 dup rows per
run; 7 additional `is_active = false` rows carry NULL ADP columns. All 98 are
dead weight.

The staging model is the employee-number provisioner (computes
`MAX(employee_number)` to assign the next-available number for new hires), so
`--full-refresh` at staging is policy-denied. Fix the symptom downstream in
`dim_staff` instead.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql`

- [ ] **Step 1: Read `dim_staff.sql`.** Locate the CTE containing
      `SELECT DISTINCT employee_number FROM ... stg_people__employee_numbers`
      with the `-- TODO: #3637` comment.

- [ ] **Step 2: Replace the DISTINCT CTE with a filtered SELECT:**

  ```sql
  -- Before
  select distinct employee_number
  from {{ ref("stg_people__employee_numbers") }}
  -- TODO: #3637

  -- After
  select employee_number
  from {{ ref("stg_people__employee_numbers") }}
  where adp_associate_id is not null and is_active
  ```

  Remove the `-- TODO: #3637` comment — the downstream filter is now the
  intended behavior, not a workaround.

- [ ] **Step 3: Verify:**

  ```bash
  uv run dbt compile --project-dir src/dbt/kipptaf --select dim_staff
  ```

  Expected: clean compile.

- [ ] **Step 4: Commit.**

  ```bash
  git add src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql
  git commit -m "fix(dbt): filter dead-weight rows downstream in dim_staff (#3637)"
  ```

### Task 2: Split location crosswalk grains + canonical region derivation (#3633)

**Background:** `int_people__location_crosswalk` is 1 row per **alias**
(alternate spelling of `location_name`) — the source Google Sheet has multiple
rows per logical school. Two consumers rely on the alias grain
(`fct_staff_observations`, `int_topline__seats_staffed_weekly_aggregations`);
the other 7 canonical-seeking consumers use `SELECT DISTINCT` workarounds.

**Two coordinated changes:**

1. Create a new `stg_people__locations` staging model at canonical-school grain
   (1 row per logical school).
2. Derive canonical `region` from `dagster_code_location` (values `kippnewark` /
   `kippcamden` / `kippmiami` / `kipppaterson`), and rename the existing
   `region` column (which holds legal-entity names like "TEAM Academy Charter
   School", matching `dim_regions.legal_entity`) to `business_unit` — aligning
   with the ADP/staff-side convention on
   `dim_work_assignment_organizational_units.business_unit_*`.

The canonical region derivation is what unblocks Conformed-domain R9 removes and
structural FK adds in Phase 2.

**Files:**

- Create: `src/dbt/kipptaf/models/people/staging/stg_people__locations.sql`
- Create:
  `src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml`
- Modify:
  `src/dbt/kipptaf/models/people/intermediate/properties/int_people__location_crosswalk.yml`
  (add `unique` test on `location_name` to document the alias grain).
- Modify 7 canonical-seeking consumers to use `stg_people__locations`:
  `dim_locations.sql`, `dim_school_calendars.sql`,
  `dim_student_enrollments.sql`, `dim_course_sections.sql`,
  `dim_assessment_targets.sql`, `fct_student_attendance_daily.sql`,
  `fct_student_attendance_interventions.sql`.
- Modify: `src/dbt/kipptaf/CLAUDE.md` — "Known Upstream Issues" section gets the
  grain split documented.

- [ ] **Step 1: Rediscover the consumer set.**

  ```bash
  grep -rn "int_people__location_crosswalk" src/dbt/kipptaf/models/
  grep -rn "#3633" src/dbt/kipptaf/models/
  ```

  Classify each hit:
  - Canonical-seeking: has `SELECT DISTINCT` + `-- TODO: #3633` on the crosswalk
    CTE.
  - Alias-seeking: joins on `location_name` as an alternate spelling (e.g.
    `fct_staff_observations` on `gro.school_name`).

  Canonical-seeking consumers (7) get rerouted. Alias-seeking consumers (3:
  `fct_staff_observations`, `int_people__staff_roster_history`,
  `int_topline__seats_staffed_weekly_aggregations`) stay on the int model.

- [ ] **Step 2: Create `stg_people__locations.sql`.**

  Read from
  `{{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }}`
  directly (skip the existing `stg_google_sheets__people__location_crosswalk` so
  a future Google-Sheet refactor with cleaner grain can reuse this model name).
  Left-join `src_google_sheets__people__campus_crosswalk` to populate
  `campus_name`.

  Apply these column transformations in the `renamed` CTE:

  ```sql
  lc.name,
  lc.abbreviation,
  lc.grade_band,
  lc.powerschool_school_id,
  lc.deanslist_school_id,
  lc.reporting_school_id,
  lc.is_campus,
  lc.is_pathways,
  lc.dagster_code_location,
  lc.head_of_schools_employee_number,
  lc.clean_name as location_name,
  lc.region as business_unit,

  case lc.dagster_code_location
      when 'kippnewark' then 'Newark'
      when 'kippcamden' then 'Camden'
      when 'kippmiami' then 'Miami'
      when 'kipppaterson' then 'Paterson'
  end as region,

  cc.name as campus_name,
  ```

  Dedup via `dbt_utils.deduplicate` with
  `partition_by="powerschool_school_id, dagster_code_location, location_name, is_pathways"`
  and `order_by="name asc"` (deterministic tie-breaker; document the choice in a
  SQL comment).

- [ ] **Step 3: Create the properties YAML.**

  Declare 13 columns (the 12 in the final SELECT plus the new `region`) with
  `data_type` and qualitative descriptions. Add a
  `dbt_utils.unique_combination_of_columns` test on the four-column grain key.
  Add `not_null` on the grain-key columns. List columns with `data_tests:`
  first.

- [ ] **Step 4: Add `unique` test on
      `int_people__location_crosswalk.location_name`** to document the alias
      grain.

- [ ] **Step 5: Reroute 7 canonical-seeking consumers.** For each file from Step
      1's canonical-seeking list:
  - Replace the `SELECT DISTINCT ... FROM ref("int_people__location_crosswalk")`
    CTE with `SELECT ... FROM ref("stg_people__locations")`.
  - Drop the `location_` prefix from join keys / surrogate-key inputs that came
    from the previously-prefixed intermediate columns
    (`location_powerschool_school_id` → `powerschool_school_id`,
    `location_clean_name` → `location_name`, etc.).
  - Preserve per-consumer filters (`not is_pathways`, Whittier exclusion).
  - Remove `-- TODO: #3633` comments.

- [ ] **Step 6: Update `src/dbt/kipptaf/CLAUDE.md`** "Known Upstream Issues"
      section. Replace the stale "duplicate" description of
      `int_people__location_crosswalk` with the grain split: this model is the
      alias grain, `stg_people__locations` is the canonical grain.

- [ ] **Step 7: Verify.**

  ```bash
  uv run dbt compile --project-dir src/dbt/kipptaf --select stg_people__locations+
  ```

  Expected: `stg_people__locations` compiles; all 7 rerouted consumers compile
  without the DISTINCT workaround.

- [ ] **Step 8: Commit.**

  ```bash
  git add src/dbt/kipptaf/models/people/staging/stg_people__locations.sql \
          src/dbt/kipptaf/models/people/staging/properties/stg_people__locations.yml \
          src/dbt/kipptaf/models/people/intermediate/properties/int_people__location_crosswalk.yml \
          src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql \
          src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql \
          src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql \
          src/dbt/kipptaf/models/marts/dimensions/dim_course_sections.sql \
          src/dbt/kipptaf/models/marts/dimensions/dim_assessment_targets.sql \
          src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql \
          src/dbt/kipptaf/models/marts/facts/fct_student_attendance_interventions.sql \
          src/dbt/kipptaf/CLAUDE.md
  git commit -m "feat(dbt): add stg_people__locations canonical-grain crosswalk with canonical region (#3633)"
  ```

---

## Phase 2 — Per-domain mart changes

Each task below applies the Procedure section once per listed model, using the
inventory as the source of truth for specific rename targets, remove sets, and
add derivations. One commit per domain; commit message template:

```text
refactor(dbt): rename mart columns - <Domain> domain per #3643
```

Where per-domain notes below call out Group 3 deferrals, special type coercions,
or coverage-gap exceptions, follow those exactly — the inventory on its own does
not encode those qualifications.

Recommended execution order: Conformed first (cross-cutting FKs land before
downstream facts reference them), then IT / Course / Staffing as warm-up, then
the medium domains, then Observation (model renames cascade via `ref()`), then
Staff (largest). Completed tasks follow this order.

### Task 3: IT domain (1 model — `fct_support_tickets`)

**Inventory counts:** 9 renames, 1 remove.

**Key changes:**

- Rename pattern R4 on timestamps: `created_at`, `initially_assigned_at`,
  `assignee_updated_at`, `solved_at` → `*_timestamp` suffix; `created_date` →
  `ticket_created_date` for parallelism with `ticket_subject` / `ticket_url`.
- Rename pattern R2 on Zendesk jargon: `assignee_stations` →
  `agent_reassignment_count`, `group_stations` → `group_reassignment_count`.
- Rename R6: `category` → `ticket_category`, `reply_time_in_minutes_business` →
  `business_minutes_to_first_reply`.
- Remove `ticket_id` (R9 via `support_ticket_key`; its unique+not_null test is
  redundant with the surrogate key's).
- Description fix on `ticket_status`: current YAML description is a PowerSchool
  copy-paste ("0=user-created, 3=auto-created"); replace with
  `Zendesk ticket workflow status (closed, open, new, pending, solved).` and
  delete the erroneous `config.meta` block.

- [ ] **Step 1:** Filter inventory for `model='fct_support_tickets'`.
- [ ] **Step 2:** Apply the Procedure to `fct_support_tickets`.
- [ ] **Step 3:** `uv run dbt compile ... --select fct_support_tickets`.
- [ ] **Step 4:** Commit.

### Task 4: Course domain (4 models)

**Models:** `bridge_course_section_teachers`, `bridge_course_section_terms`,
`dim_course_sections`, `dim_courses`.

**Inventory counts:** 7 renames, 5 removes.

**Key changes:**

- `bridge_course_section_teachers`: effective-date SCD renames
  (`effective_date_start` → `effective_start_date`, `effective_date_end` →
  `effective_end_date`); remove `sections_dcid`, `employee_number`,
  `teachernumber` (R9 via FK traversal). Update the
  `unique_combination_of_columns` test to reference the renamed
  `effective_start_date`.
- `bridge_course_section_terms`: remove `sections_dcid`, `term_code` (R9).
- `dim_course_sections`: rename `section_number` → `section_identifier` (R6,
  Ed-Fi `edFi_gradeReference.sectionIdentifier`).
- `dim_courses`: rename `course_number` → `course_code`, `course_name` →
  `course_title`, `discipline` → `academic_subject`, `credit_hours` → `credits`
  (R6, all Ed-Fi cognates).

- [ ] **Step 1:** Filter inventory for `domain='Course'`.
- [ ] **Step 2:** Apply the Procedure to each of the 4 models.
- [ ] **Step 3:**
      `uv run dbt compile ... --select bridge_course_section_teachers bridge_course_section_terms dim_course_sections dim_courses`.
- [ ] **Step 4:** Commit.

### Task 5: Staffing domain (1 model — `dim_staffing_positions`)

**Inventory counts:** 5 renames, 7 removes.

**Key changes + special cases:**

- Rename R2: `teammate_staff_key` → `incumbent_staff_key` (KIPP jargon);
  description must be rewritten — existing copy still references "teammate" as
  the column identity. Replace with:
  `Foreign key to dim_staff for the incumbent (staff member filling the position). Surrogate key derived from the teammate employee number. Nullable — open positions have no incumbent.`
- Rename R3 with type coercion: `plan_status` → `is_active` (string → boolean).
  SQL:

  ```sql
  if(plan_status in ('Active', 'TRUE'), true, false) as is_active,
  ```

  This matches the sibling `int_seat_tracker__snapshot` /
  `stg_google_appsheet__seat_tracker__log_archive` pattern. YAML
  `data_type: boolean`; description reads
  `Whether this position is active in the staffing plan. True when plan_status is 'Active' or 'TRUE'; false otherwise (including 'Inactive' and null).`

- Rename R6: `job_title` → `position_title` (Ed-Fi
  `openStaffPosition.position_title`).
- Rename R4: `effective_date_start` / `effective_date_end` →
  `effective_start_date` / `effective_end_date`.
- Removes: `staffing_model_id` (plumbing); `entity`, `grade_band` (R9, blocked
  cascade — accept traversal loss per spec Region cascade section);
  `home_work_location_name`, `location_short_name`, `recruiter_employee_number`,
  `teammate_employee_number` (R9 via FK).
- Model-level description rewrite: existing enumerates removed/renamed columns
  (`entity`, `grade_band`, `plan status`, `job title`, `teammate`). Replace to
  reflect new identities.

- [ ] **Step 1:** Filter inventory for `model='dim_staffing_positions'`.
- [ ] **Step 2:** Apply the Procedure with special cases above.
- [ ] **Step 3:** `uv run dbt compile ... --select dim_staffing_positions`.
- [ ] **Step 4:** Commit.

### Task 6: Talent domain (3 models)

**Models:** `dim_job_candidates`, `dim_job_postings`,
`fct_job_candidate_applications`.

**Inventory counts:** 24 renames, 26 removes, 1 add.

**Key changes + special cases:**

- `dim_job_candidates`: 4 R6 renames stripping `candidate_` prefix
  (`candidate_first_name` → `first_name`, etc.); 4 plumbing removes.
- `dim_job_postings`: 5 R6 renames (`job_title` → `position_title`,
  `department_internal` → `department_name`, `department_org_field_value` →
  `organizational_hierarchy`, etc.). The surrogate-key macro
  `generate_surrogate_key(["job_title", "department_internal", "job_city"])`
  references CTE-internal column names — do NOT change the macro input.
- `fct_job_candidate_applications`: 15 renames (11 R4 `_datetime` →
  `_timestamp`, `source` → `application_source`, others); 22 plumbing/R9
  removes; 1 structural add `shared_with_location_key`.
  - **R4 type coercion** on `application_status_interview_performance_task_date`
    → `application_status_interview_performance_task_timestamp`: upstream is
    string; coerce at the mart layer (minimize blast radius vs. staging edit):

    ```sql
    safe_cast(
        application_status_interview_performance_task_date as timestamp
    ) as application_status_interview_performance_task_timestamp,
    ```

    YAML `data_type: timestamp`. `safe_cast` (not `cast`) so malformed strings
    produce NULL rather than failing the model.

  - **Structural add** `shared_with_location_key`: FK to `dim_locations` via
    `generate_surrogate_key(["school_shared_with"])` wrapped for nullability
    (`school_shared_with` is nullable). `dim_locations.location_key` hashes
    `location_name`; `school_shared_with` holds school-name strings, so hashes
    align for matched rows.
  - **Coverage-gap exception** on `shared_with_location_key`: ~20% of rows carry
    `school_shared_with` values that don't exist in
    `dim_locations.location_name` (notably `KIPP High School`). Ship the
    `relationships` test at `severity: warn` with a TODO referencing
    [#3672](https://github.com/TEAMSchools/teamster/issues/3672). See the
    Procedure's "Coverage-gap exception" section for the YAML shape.
  - Model-level description update: current enumerates `dim_job_candidates` and
    `dim_job_postings` FKs; add `dim_locations` after the structural add.

- [ ] **Step 1:** Filter inventory for `domain='Talent'`.
- [ ] **Step 2:** Apply the Procedure with special cases above.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_job_candidates dim_job_postings fct_job_candidate_applications`.
- [ ] **Step 4:** Commit.

### Task 7: Survey domain (7 models)

**Models:** `bridge_survey_questions`, `dim_survey_administrations`,
`dim_survey_expectations`, `dim_survey_questions`, `dim_surveys`,
`fct_survey_responses`, `fct_survey_submissions`.

**Inventory counts:** 5 renames, 11 removes.

**Key changes:**

- `dim_surveys.subject_area` → `category` (R6);
  `dim_survey_expectations.respondent_population` → `respondent_type` (R6);
  `fct_survey_submissions.respondent_population` → `respondent_type` (R6);
  `dim_survey_administrations.response_deadline` → `response_deadline_date`
  (R4); `fct_survey_submissions.date_submitted` → `submission_timestamp` (R4 —
  upstream `int_surveys__survey_responses` already emits `timestamp`, so this is
  an alias rename with YAML `data_type` sanity check, no cast).
- `dim_survey_administrations` removes `survey_id`, `survey_name`, `term_code`,
  `term_name` (R9). The downstream `dim_survey_expectations` previously joined
  to pick up `survey_name` from administrations; this task adds an inner-join to
  `dim_surveys` so `survey_name` is sourced directly via `survey_key`.
  `dim_surveys.survey_key` is unique, so the join cannot fan out.
- Other removes: `fct_survey_responses.question_shortname`,
  `survey_response_id`, `survey_id` (all R9 / plumbing).

- [ ] **Step 1:** Filter inventory for `domain='Survey'`.
- [ ] **Step 2:** Apply the Procedure to each of the 7 models. Ensure the
      `dim_survey_expectations` CTE refactor preserves semantics.
- [ ] **Step 3:**
      `uv run dbt compile ... --select bridge_survey_questions dim_survey_administrations dim_survey_expectations dim_survey_questions dim_surveys fct_survey_responses fct_survey_submissions`.
- [ ] **Step 4:** Commit.

### Task 8: College domain (2 models)

**Models:** `dim_college_enrollments`, `dim_colleges`.

**Inventory counts:** 3 renames, 4 removes.

**Key changes:**

- `dim_colleges`: `college_state` → `state_abbreviation` (R6);
  `is_strong_oos_option` → `is_strong_out_of_state_option` (R7, spell out
  `oos`); `selectivity` → `selectivity_tier` (R6); remove `two_year_four_year`
  (plumbing — dead in production; redundant with `account_type`). Upstream CTEs
  may reference `two_year_four_year` only to feed the removed column — clean up
  the dead derivation.
- `dim_college_enrollments`: remove `student_number`, `college_code_branch` (R9
  via FK); `degree_pursued` (plumbing — no upstream source). The upstream
  `degree_pursued` aggregation (`max()`) in a CTE becomes dead — remove it.

- [ ] **Step 1:** Filter inventory for `domain='College'`.
- [ ] **Step 2:** Apply the Procedure to both models, cleaning dead upstream
      derivations.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_college_enrollments dim_colleges`.
- [ ] **Step 4:** Commit.

### Task 9: Attendance domain (4 models)

**Models:** `dim_student_attendance_intervention_types`,
`fct_student_attendance_daily`, `fct_student_attendance_interventions`,
`fct_student_attendance_streaks`.

**Inventory counts:** 6 renames, 12 removes, 2 adds.

**Key changes + special cases:**

- `dim_student_attendance_intervention_types`: `commlog_reason` →
  `family_communication_reason` (R2, DeansList jargon); remove `region` (R9);
  add `region_key` FK to `dim_regions`. The derivation hashes the canonical
  region value (from `stg_people__locations` lookup post-Phase-1) so hashes
  match `dim_regions.region_key`.
- `fct_student_attendance_daily`:
  - **R3 type coercions on 6 countable flags:** `is_absent`, `is_tardy`,
    `is_ontime`, `is_oss`, `is_iss`, `is_suspended` — float → int64:

    ```sql
    cast(is_absent as int64) as is_absent,
    ```

    Update each YAML `data_type: float64` → `int64`. These are `keep` actions in
    the inventory (no name change) — the coercion is a type-only change per the
    updated R3 rule.

  - Rename `is_present_weighted` → `present_weight` (R3, **keep float64** — this
    is the genuinely-fractional weight column).
  - Rename `term` → `term_code` (R6).
  - Remove `student_number` (R9).

- `fct_student_attendance_interventions`:
  - Rename `intervention_status` → `is_complete` (R3, string → boolean cast):

    ```sql
    case intervention_status
        when 'Complete' then true
        when 'Incomplete' then false
    end as is_complete,
    ```

    Read the actual string enum values first and adjust the case arms to match
    production data. YAML `data_type: boolean`; description updated to reflect
    boolean semantics.

  - Rename `is_ca_exception` → `is_chronic_absence_exception` (R2).
  - Remove 7 `commlog_*` columns (R9 via new `family_communication_key`) and
    `intervention_status_required_int` (plumbing — redundant).
  - Add `family_communication_key` FK: derive via
    `generate_surrogate_key([<upstream commlog_id>])`, matching whatever
    `fct_family_communications.family_communication_key` hashes. Check that
    model's SQL to identify the input column. Wrap for nullability.

- `fct_student_attendance_streaks`: rename `streak_type` → `attendance_code`
  (R6); remove `student_number` (R9).

- [ ] **Step 1:** Filter inventory for `domain='Attendance'`.
- [ ] **Step 2:** Apply the Procedure plus the type coercions and FK adds.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_student_attendance_intervention_types fct_student_attendance_daily fct_student_attendance_interventions fct_student_attendance_streaks`.
- [ ] **Step 4:** Commit.

### Task 10: Conformed domain (5 models, cross-cutting)

**Models:** `dim_dates`, `dim_locations`, `dim_regions`, `dim_school_calendars`,
`dim_terms`.

**Inventory counts:** 6 renames, 7 removes, 7 adds. **4 of the 7 adds are Group
3 deferrals** (dim_locations address unification) — skip them.

**In-scope changes (6 renames, 7 removes, 3 adds):**

- `dim_dates`: 4 R6/R4 renames (`week_start_date` → `calendar_week_start_date`,
  `week_end_date` → `calendar_week_end_date`, `week_start_monday` →
  `school_week_start_date`, `week_end_sunday` → `school_week_end_date`).
- `dim_regions`: rename `region` → `region_name` (R6). The `region_key`
  surrogate hashes the upstream `region` value; that value is unchanged, so the
  hash is byte-identical. Do NOT change the `generate_surrogate_key(["region"])`
  input.
- `dim_locations`:
  - Remove `region` (R9 via new `region_key`), `powerschool_school_id`
    (plumbing), `deanslist_school_id` (plumbing).
  - Add `region_key` FK (Group 1/2 structural add). Derivation:

    ```sql
    if(
        region is not null,
        {{ dbt_utils.generate_surrogate_key(["region"]) }},
        cast(null as string)
    ) as region_key,
    ```

    The `region` input is now the canonical region from the Phase-1 staging fix
    — hashes match `dim_regions.region_key`.

  - **DEFERRED** (inventory rows 889–892, Group 3): `address_line_one`,
    `address_line_two`, `city`, `postal_code` adds. Do NOT apply.

- `dim_terms`:
  - Remove `region`, `school_id` (R9 via new FKs); `powerschool_year_id`,
    `powerschool_term_id` (plumbing).
  - Add `region_key`, `location_key` FKs. Derive both via a CTE that joins to
    `stg_people__locations` on
    `dim_terms.school_id = stg_people__locations.powerschool_school_id` (filter
    `not is_pathways and location_name <> 'KIPP Whittier Elementary'` to match
    `dim_locations` dedup). The resulting `location_name` and `region` become
    the hash inputs for the two FKs, matching the parent dims' derivations.
  - `term_key` surrogate-key input stays
    `["type", "code", "name", "start_date", "region", "school_id"]` (with
    reserved-word backticks where needed) — the raw `region` / `school_id`
    upstream values still exist in the source CTE; hash stable.
  - Rename `lockbox_date` → `data_freeze_date` (R2, KIPP jargon).
- `dim_school_calendars`: no changes per inventory (all `keep`). Include in the
  verification `--select` to confirm no cascade breakage.

- [ ] **Step 1:** Filter inventory for `domain='Conformed'`.
- [ ] **Step 2:** Apply the Procedure per model, skipping the 4 deferred
      `dim_locations` address adds. Confirm `dim_terms` uniqueness
      (`count(*) = count(distinct term_key)`) after adding the lookup join.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_dates dim_locations dim_regions dim_school_calendars dim_terms`;
      also run full-project compile to confirm no cascade breakage.
- [ ] **Step 4:** Commit.

### Task 11: Behavioral domain (3 models)

**Models:** `fct_behavioral_consequences`, `fct_behavioral_incidents`,
`fct_family_communications`.

**Inventory counts:** 5 renames, 9 removes, 2 adds.

**Key changes + special cases:**

- `fct_behavioral_consequences`: `num_days` → `days_assigned`, `num_periods` →
  `periods_assigned` (R6); remove `incident_id`, `incident_penalty_id`
  (plumbing).
- `fct_behavioral_incidents`:
  - Rename `infraction` → `infraction_description` (R6).
  - Remove `student_number`, `incident_id` (plumbing), `referring_staff_name`,
    `referring_staff_id` (R9 via new FK).
  - Add `referring_staff_key` FK to `dim_staff`. DeansList has no direct
    `employee_number` crosswalk, so derive via the only available bridge:
    `stg_deanslist__users` (on `dl_user_id`) → `email` →
    `int_people__staff_roster` (on `work_email`) → `employee_number` →
    `generate_surrogate_key(["sr.employee_number"])`. Both joins are LEFT so
    unmatched fact rows are preserved. `int_people__staff_roster` is unique per
    `employee_number` (verified in its YAML); no fan-out.
  - Model-level description update: current version claims "no employee_number
    available from DeansList" — this task adds that resolution. Update to
    describe the FK resolution via email lookup.
- `fct_family_communications`:
  - Rename `status` → `communication_outcome` (R6); `communication_datetime` →
    `communication_timestamp` (R4).
  - Remove `student_number`, `record_id` (plumbing), `staff_name` (R9 via new
    FK).
  - Add `staff_key` FK to `dim_staff`. Same DeansList-email resolution as above.

- [ ] **Step 1:** Filter inventory for `domain='Behavioral'`.
- [ ] **Step 2:** Apply the Procedure with FK adds via the email-lookup chain;
      update the `fct_behavioral_incidents` model-level description.
- [ ] **Step 3:**
      `uv run dbt compile ... --select fct_behavioral_consequences fct_behavioral_incidents fct_family_communications`.
- [ ] **Step 4:** Commit.

### Task 12: Student domain (5 models)

**Models:** `bridge_student_contacts`, `dim_student_contact_persons`,
`dim_student_enrollments`, `dim_student_section_enrollments`, `dim_students`.

**Inventory counts:** 8 renames, 5 removes, 2 adds.

**Key changes + special cases:**

- `bridge_student_contacts`: remove `student_number` (R9).
- `dim_student_contact_persons`: remove `_dbt_source_relation`,
  `powerschool_person_id` (plumbing); rename `address` → `home_address` (R6).
  `email` and `phone` are flagged as 100%-null model bugs in the spec — **KEEP**
  them both; do not remove. The primary-key description should reference the
  upstream `personid` column (not the removed `powerschool_person_id`).
- `dim_student_enrollments`: remove `school_level` (R9 via location_key); rename
  `enroll_status` → `enrollment_status` (R1, spell out).
- `dim_student_section_enrollments`: remove `student_number` (R9); rename
  `date_enrolled` → `entry_date` (R4), `date_left` → `exit_date` (R4).
- `dim_students`:
  - Renames: `local_student_identifier` → `lea_student_identifier` (R6,
    KIPP-as-LEA perspective; **must have `not_null` test per spec** — see spec
    "Structural additions" line 128); `gender` → `gender_identity` (R1);
    `lunch_status` → `meal_eligibility_status` (R6); `ethnicity` → `race` (R1).
    The `race` description must NOT claim Hispanic ethnicity is separated into
    `is_hispanic` — no such column exists on `dim_students` (the inventory's
    reviewer_notes on that row were inaccurate).
  - Structural adds (per spec lines 117–145 — four-ID model):
    - `district_student_identifier` (**`data_type: string`** — upstream
      `int_extracts__student_enrollments.secondary_state_studentnumber` is
      string). Host-district identifier: MDCPS for Miami; NULL for NJ regions
      where the host-district ID is not surfaced upstream. Generalizes the
      previously Miami-only concept.
    - `salesforce_contact_id` (`data_type: string`). KIPPADB Salesforce contact
      ID; sourced from upstream `salesforce_id` alias.

- [ ] **Step 1:** Filter inventory for `domain='Student'`; read spec lines
      117–180 for the multi-ID structural additions.
- [ ] **Step 2:** Apply the Procedure per model. Confirm
      `lea_student_identifier` carries `not_null`; `district_student_identifier`
      is `string`.
- [ ] **Step 3:**
      `uv run dbt compile ... --select bridge_student_contacts dim_student_contact_persons dim_student_enrollments dim_student_section_enrollments dim_students`.
- [ ] **Step 4:** Commit.

### Task 13: Gradebook domain (4 models)

**Models:** `fct_grades_assignments`, `fct_grades_category`, `fct_grades_gpa`,
`fct_grades_term`.

**Inventory counts:** 7 renames, 9 removes, 2 adds. **Group 3 score-split
deferred:** skip 2 removes (`score`, `score_type`) and 2 adds (`points_earned`,
`numeric_grade_earned`) on `fct_grades_assignments`.

**In-scope changes (7 renames, 7 removes, 0 adds):**

- `fct_grades_assignments`: `points_possible` → `max_points` (R6, Ed-Fi); remove
  `student_number` (R9). **Deferred:** keep `score`, `score_type`; do not add
  `points_earned`, `numeric_grade_earned`.
- `fct_grades_category`: remove `student_number`, `term_code` (R9).
- `fct_grades_gpa`: rename 3 R6 (`cumulative_y1_gpa` → `cumulative_gpa`,
  `cumulative_y1_gpa_unweighted` → `cumulative_gpa_unweighted`,
  `cumulative_y1_gpa_projected` → `cumulative_gpa_projected`); remove
  `student_number`, `term_name` (R9).
- `fct_grades_term`: rename R1/R6 (`citizenship` → `citizenship_grade`,
  `grade_points` → `grade_points_earned`); rename R3 with type coercion
  `exclude_from_gpa` → `is_excluded_from_gpa` (int64 0/1 → boolean):

  ```sql
  cast(exclude_from_gpa as bool) as is_excluded_from_gpa,
  ```

  YAML `data_type: boolean`. Remove `student_number`, `term_code` (R9).

- [ ] **Step 1:** Filter inventory for `domain='Gradebook'`; skip the 4 deferred
      rows.
- [ ] **Step 2:** Apply the Procedure with the int → bool cast.
- [ ] **Step 3:**
      `uv run dbt compile ... --select fct_grades_assignments fct_grades_category fct_grades_gpa fct_grades_term`.
- [ ] **Step 4:** Commit.

### Task 14: Observation domain (8 models, includes model renames)

**Models:** `dim_staff_observation_expectations`,
`dim_staff_observation_microgoal_types`,
`dim_staff_observation_rubric_measurements`, `dim_staff_observation_rubrics`,
`dim_staff_observation_types`, `fct_staff_observation_microgoals`,
`fct_staff_observation_scores`, `fct_staff_observations`.

**Inventory counts:** 19 renames, 36 removes, 2 adds.

**Model renames (spec lines 147–158):** two models carry KIPP `microgoal` jargon
and get renamed:

| Current                                 | Renamed                            |
| --------------------------------------- | ---------------------------------- |
| `dim_staff_observation_microgoal_types` | `dim_staff_observation_goal_types` |
| `fct_staff_observation_microgoals`      | `fct_staff_observation_goals`      |

All `*_microgoal_*` column renames in the inventory derive from these model
renames — once the models are renamed, column renames follow naturally without
needing per-column edits.

Cascading changes:

- Rename the `.sql` file and its `properties/<name>.yml` file.
- Update every `ref()` to the old model names in the repo (use
  `grep -rn "fct_staff_observation_microgoals\|dim_staff_observation_microgoal_types" src/dbt/kipptaf/`).
- Check `dbt_project.yml` for any explicit per-model configuration at the old
  names.

**Other key changes:**

- `fct_staff_observations`:
  - Rename `glows` → `positive_feedback` (R2, KIPP jargon); `grows` →
    `growth_areas` (R2).
  - Keep `observation_score`.
  - Remove `eval_date`, `assignment_status`, `term_type`, `term_code`,
    `term_name`, `term_start_date`, `term_end_date` (R9 via `term_key`).
  - Add `staff_observation_type_key` and `staff_observation_rubric_key` FKs.
- `dim_staff_observation_rubric_measurements`: remove `measurement_row_style`
  (plumbing).
- `dim_staff_observation_rubrics`: remove `district` (plumbing).

**Execution order:** apply model renames first (they affect file paths and
refs); then per-model column changes.

- [ ] **Step 1:** Filter inventory for `domain='Observation'`.
- [ ] **Step 2:** Rename the two model files + YAMLs; grep and update all
      `ref()` calls in the project; then apply the Procedure per model.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_staff_observation_expectations dim_staff_observation_goal_types dim_staff_observation_rubric_measurements dim_staff_observation_rubrics dim_staff_observation_types fct_staff_observation_goals fct_staff_observation_scores fct_staff_observations`.
- [ ] **Step 4:** Commit.

### Task 15: Assessment domain (6 models)

**Models:** `dim_assessment_comparisons`, `dim_assessment_targets`,
`dim_assessments`, `dim_student_assessment_expectations`,
`fct_assessment_scores_enrollment_scoped`,
`fct_assessment_scores_student_scoped`.

**Inventory counts:** 10 renames, 24 removes, 4 adds.

**Key changes + special cases:**

- `dim_assessments`:
  - Rename `title` → `assessment_title`, `subject_area` → `academic_subject`,
    `scope` → `assessment_category` (all R6). **Coexistence flag:**
    `dim_assessments` also has an existing `assessment_scope` column per spec
    "Structural follow-ups — `dim_assessments` scope vs assessment_scope
    untangling". Keep both — the rename produces `assessment_category`
    (internal/state/college grouping), while `assessment_scope` (values
    "enrollment" etc.) remains its own column. Verify they're semantically
    distinct during execution.
  - Structural adds: `combined_academic_subject`, `aligned_academic_subject`,
    `credit_category`. Determine upstream sources from `dim_assessments.sql` and
    any relevant staging/intermediate models before implementing; if any of the
    three lack clear upstream sources, flag BLOCKED.
- `dim_assessment_targets`: rename `illuminate_subject_area` →
  `academic_subject` (R1); remove `school_level`, `region` (R9).
- `dim_student_assessment_expectations`: rename `administered_at` →
  `administered_date` (R4 — verify upstream is actually a date-typed column
  despite the `_at` suffix; if it's a timestamp, treat as R4 timestamp rename
  instead); rename `scope` → `assessment_category` (R6); remove 8 columns
  (R9/plumbing); add `student_key` FK to `dim_students` (match its hash
  derivation).
- `fct_assessment_scores_enrollment_scoped`: rename `scope` →
  `assessment_category`, `score_source` → `score_provider` (R6); remove 6
  columns (R9/plumbing).
- `fct_assessment_scores_student_scoped`: rename `rn_highest` → `score_rank`
  (R1), `score_source` → `score_provider` (R1); remove 8 columns
  (`student_number`, `assessment_scope`, `subject_area`, `percent_correct`,
  `course_discipline`, `aligned_subject_area`, `aligned_subject`).
- `dim_assessment_comparisons`: remove `region` (R9).

- [ ] **Step 1:** Filter inventory for `domain='Assessment'`.
- [ ] **Step 2:** Apply the Procedure per model. Handle the three
      `dim_assessments` structural adds carefully; verify the `assessment_scope`
      / `assessment_category` coexistence.
- [ ] **Step 3:**
      `uv run dbt compile ... --select dim_assessment_comparisons dim_assessment_targets dim_assessments dim_student_assessment_expectations fct_assessment_scores_enrollment_scoped fct_assessment_scores_student_scoped`.
- [ ] **Step 4:** Commit.

### Task 16: Staff domain (14 models, largest)

**Models:** `dim_staff`, `dim_staff_status`, `dim_staff_work_assignments`,
`dim_work_assignment_jobs`, `dim_work_assignment_locations`,
`dim_work_assignment_organizational_units`,
`dim_work_assignment_reporting_relationships`, `dim_work_assignment_status`,
`dim_work_assignment_types`, `fct_staff_attrition`,
`fct_staff_benefits_enrollments`, `fct_staff_membership_enrollments`,
`fct_work_assignment_additional_earnings`, `fct_work_assignment_compensation`.

**Inventory counts:** 54 renames, 24 removes, 3 adds. Largest domain — consider
splitting the commit into two if the diff is unreviewably large: `dim_staff` +
`dim_staff_work_assignments` first, then the SCD2 dims + facts. Same commit
message; append `(part 1/2)` / `(part 2/2)` if split.

**Group 3 deferrals** on `dim_work_assignment_locations`: do NOT remove the 8
address columns, do NOT add `location_key`. Apply only the 3 SCD-date renames
(`effective_date_start` → `effective_start_date`, etc.) and `is_current_record`
→ `is_current`.

**Key in-scope changes:**

- `dim_staff`:
  - Rename `employee_number` → `staff_unique_id` (R6, Ed-Fi exact match);
    `formatted_name` → `full_name` (R6, drop ADP jargon); `given_name` →
    `first_name` (R6); `family_name_1` → `last_name` (R6);
    `race_ethnicity_reporting` → `race` (R6); `personal_cell` →
    `personal_cell_phone` (R6, parallel with `work_email`); `sam_account_name` →
    `active_directory_username` (R1, drop Microsoft SAM legacy term).
  - Type note on `staff_unique_id`: stays `int64`.
    `dbt_utils.generate_surrogate_key` stringifies inputs — no hash change.
- `dim_staff_work_assignments`:
  - 12 renames incl. 7 `*_code__code_value` / `*_name` ADP-structure flattenings
    (see inventory `reviewer_notes`); 4 `worker_time_profile__*` renames;
    `time_and_attendance_indicator` → `is_time_and_attendance_active`;
    `full_time_equivalence_ratio` → `full_time_equivalency`.
  - Remove 6 columns.
  - Add `time_service_supervisor_staff_key` FK to `dim_staff`.
- All SCD2 dims uniform renames: `effective_date_start` →
  `effective_start_date`, `effective_date_end` → `effective_end_date`,
  `is_current_record` → `is_current`.
- `dim_work_assignment_jobs`: `job_title` → `position_title`; `job_code_name` →
  `job_code_description`.
- `dim_work_assignment_reporting_relationships`: 6 `manager_*` removes (R9); add
  `manager_staff_key` FK.
- `fct_work_assignment_compensation`: `annual_rate` → `annual_wage`;
  `hourly_rate` → `hourly_wage`.
- `fct_staff_benefits_enrollments`: remove `enrollment_status` (100% `'Active'`
  in production — dead).

- [ ] **Step 1:** Filter inventory for `domain='Staff'`.
- [ ] **Step 2:** Apply the Procedure per model. Honor Group 3 deferrals on
      `dim_work_assignment_locations`. Consider two commits if the diff is large
      (`dim_staff` + `dim_staff_work_assignments` in one; remaining 12 models in
      another).
- [ ] **Step 3:** `uv run dbt compile ... --select <all 14 models>`.
- [ ] **Step 4:** Commit (one or two commits per Step 2 decision).

---

## Phase 3 — Verification and cleanup

### Task 17: Exposure sweep

**Files:** `src/dbt/kipptaf/models/exposures/**/*.yml`.

- [ ] **Step 1: Enumerate renamed columns.**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit
  uv run --with pandas python <<'PY' > /tmp/renames.tsv
  import pandas as pd
  df = pd.read_csv(
      'docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv',
      keep_default_na=False, na_values=[''],
  )
  for _, r in df[df['action'] == 'rename'].iterrows():
      print(f"{r['current_column']}\t{r['proposed_name']}")
  PY
  ```

- [ ] **Step 2: Grep exposures for each old name.**

  ```bash
  cd src/dbt/kipptaf/models/exposures
  while IFS=$'\t' read -r old_name new_name; do
      matches=$(grep -rn "$old_name" . || true)
      if [ -n "$matches" ]; then
          echo "=== $old_name → $new_name ==="
          echo "$matches"
      fi
  done < /tmp/renames.tsv
  ```

- [ ] **Step 3: Update each match.** Replace the old column name with the new
      name in the exposure YAML. External tools (Tableau workbooks, Google
      Sheets destinations) that reference these columns are outside the repo —
      flag those as follow-up work but don't block this PR.

- [ ] **Step 4: Commit (only if exposures changed).**

  ```bash
  git add src/dbt/kipptaf/models/exposures/
  git commit -m "refactor(dbt): update exposures for renamed mart columns per #3643"
  ```

### Task 18: Final verification + spec update + PR

- [ ] **Step 1: Full-project compile.**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit
  uv run dbt compile --project-dir src/dbt/kipptaf
  ```

  Expected: zero errors.

- [ ] **Step 2: Targeted build on modified models.**

  ```bash
  uv run dbt build --project-dir src/dbt/kipptaf \
      --select state:modified+ --target defer --full-refresh
  ```

  Expected: all tests pass, all models build. `state:modified+` expands
  downstream so any `relationships` tests that would fail due to hash-change
  cascades are caught here. Warn-severity `relationships` tests on documented
  coverage gaps (e.g. `shared_with_location_key` per #3672) will report
  warnings, not fail.

- [ ] **Step 3: Update spec's Hash-change posture with enumerated keys.**

  Edit
  [docs/superpowers/specs/2026-04-15-column-naming-audit.md](../specs/2026-04-15-column-naming-audit.md)
  section "Hash-change posture". Replace the prose description with an explicit
  list of surrogate keys whose input composition changed, their before/after
  derivation, and the expected hash-change cause. Use the compiled SQL from Step
  2 to identify changed keys precisely.

- [ ] **Step 4: Commit spec update.**

  ```bash
  git add docs/superpowers/specs/2026-04-15-column-naming-audit.md
  git commit -m "docs(spec): enumerate hash-change surrogate keys for #3643"
  ```

- [ ] **Step 5: Pre-push lint.** Trunk git hooks are not installed in worktrees,
      so run the CI check manually before pushing:

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit
  /workspaces/teamster/.trunk/tools/trunk check --ci
  ```

  Fix any reported issues.

- [ ] **Step 6: Push branch and open PR.**

  ```bash
  git push -u origin cbini/feat/claude-column-naming-audit
  gh pr create --title "refactor(dbt): mart column naming alignment + upstream prerequisites" --body "$(cat <<'EOF'
  ## Summary

  Executes the column-naming audit (#3643) bundled with the two upstream
  prerequisite fixes (#3633, #3637).

  - Applies 168 renames, 180 removes, and structural adds (Groups 1 + 2)
    per the finalized audit inventory across 67 mart models.
  - Deduplicates `stg_people__employee_numbers` and
    `int_people__location_crosswalk` upstream, removing downstream
    `SELECT DISTINCT` workarounds.
  - Derives canonical region from `dagster_code_location` in
    `stg_people__locations`, unblocking Conformed-domain R9 removes + FK
    adds; preserves the existing legal-entity names as `business_unit`.
  - Ed-Fi / CEDS aligned naming across assessment, staff, location, and
    gradebook domains.
  - Group 3 structural adds (fct_grades_assignments score split,
    dim_locations address unification + dim_work_assignment_locations FK)
    deferred to follow-up PRs under issue #3631.

  ## Test plan

  - [ ] `dbt compile` clean
  - [ ] CI `dbt build` against staging passes (warn-severity
        `shared_with_location_key` relationships test per #3672)
  - [ ] New uniqueness tests on `stg_people__employee_numbers` and
        `int_people__location_crosswalk` pass
  - [ ] Hash-change posture in the spec is updated with the enumerated
        surrogate keys whose composition changed
  - [ ] Exposure sweep complete; Tableau/Google Sheets follow-ups flagged

  Closes #3643, #3633, #3637.

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

---

## Execution notes

- **Worktree posture:** all execution in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-column-naming-audit`. `cd`
  to the worktree before any `git` or `uv run` command.
- **Commit granularity:** one commit per Phase 2 task (two for Staff if large).
  Phase 1 is 2 commits, Phase 2 is 14–15 commits, Phase 3 is 2–3 commits. Total
  target: ~18–20 commits on the branch; single squash-merge PR.
- **No test runs between domains:** only `dbt compile`. Full `dbt build` is Task
  18 to avoid redundant BQ costs.
- **Inventory CSV is append-only during execution.** Do NOT edit
  `reviewer_notes` or decisions during execution. If you discover an error, stop
  and document it separately (spec edit + issue).
- **If a cross-domain consumer fails to compile** after a rename/remove:
  classify the failing model's domain. If that domain is already completed
  (earlier in execution order), investigate immediately — an earlier commit
  missed a dependency. If the failing model is in a pending domain, log the
  failure in the DONE_WITH_CONCERNS report for the current task; the pending
  domain task will resolve it naturally.
- **Coverage-gap exceptions** (warn-severity `relationships` tests) are allowed
  but must reference a tracked GitHub issue. Do NOT downgrade to warn silently.
- **Group 3 deferrals** are tracked in #3631. Leaving their inventory rows
  unapplied is the correct behavior — the plan explicitly skips them.
