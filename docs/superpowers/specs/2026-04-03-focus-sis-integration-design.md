# Focus SIS Integration Design

## Summary

Integrate Focus SIS (PostgreSQL database) into the teamster data platform for
KIPP Miami. Focus replaces PowerSchool as the SIS for this district. Data flows
from Focus Postgres via dlt to BigQuery, then through dbt staging/intermediate
models in a new `focus` source-system project, consumed by `kippmiami` as a
local package and exposed to `kipptaf` via regional sources.

## Scope

### Phase 1 (this spec)

9 domains, ~60 tables:

| Domain            | Key tables                                                                                                                                                                                                                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Students          | `students`, `students_join_users`, `students_join_people`, `students_join_address`, `students_join_groups`, `students_join_students`, `people`, `people_join_contacts`, `address`, `student_groups`                                                                                                                                              |
| Enrollment        | `student_enrollment`, `student_enrollment_codes`, `school_gradelevels`, `schools`, `districts`, `scheduling_teams`, `attendance_calendars`, `grad_subject_programs`                                                                                                                                                                              |
| Attendance Day    | `attendance_day`, `attendance_notes`, `attendance_codes`, `marking_periods`                                                                                                                                                                                                                                                                      |
| Attendance Period | `attendance_period`, `attendance_completed`, `school_periods`                                                                                                                                                                                                                                                                                    |
| Courses/Schedule  | `courses`, `course_periods`, `schedule`, `course_subjects`, `course_weights`, `master_courses`, `course_code_directory`, `co_teachers`, `co_teacher_days`, `resources`                                                                                                                                                                           |
| Grades            | `student_report_card_grades`, `report_card_grades`, `report_card_grade_scales`, `report_card_comments`, `grad_subjects`, `grad_subject_credits`, `student_standard_grades`, `standards`, `standard_categories_1`-`4`, `standards_join_courses`, `gradebook_grades`, `gradebook_assignments`, `gradebook_assignment_types`, `gradebook_templates` |
| Discipline        | `discipline_referrals`, `discipline_incidents`, `discipline_incidents_join_referrals`, `referral_codes`, `referral_actions`, `referral_code_offenses`                                                                                                                                                                                            |
| Users             | `users`, `user_enrollment`, `user_profiles`, `permission`, `login_history`                                                                                                                                                                                                                                                                       |
| Custom Fields     | `custom_fields`, `custom_field_categories`, `custom_field_select_options`, `custom_field_log_columns`, `custom_field_log_entries`, `custom_fields_join_categories`                                                                                                                                                                               |
| Test History      | `test_history_tests`, `test_history_test_types`, `test_history_administrations`, `test_history_scores`, `test_history_parts`, `test_history_score_types`, `test_history_score_ranges`                                                                                                                                                            |

### Phase 2 (deferred)

Communication, Formbuilder, SSS (student support services), School Choice.

### Out of scope

Generic cross-SIS data mart unifying PowerSchool and Focus -- separate project.

## Architecture

### Extraction: dlt `sql_table` -> BigQuery

**Approach**: Use dlt's built-in `sql_table` standalone resource (from
`dlt.sources.sql_database`) with modern dlt 1.24.0 features. No ejected/vendored
source code. This differs from the Illuminate pattern by using `sql_table`
directly instead of wrapping `sql_database`, and by using
`reflection_level="full_with_precision"` instead of custom type adapters.

**New library: `src/teamster/libraries/dlt/focus/`**

- `assets.py`:
  - `FocusDagsterDltTranslator` -- asset keys:
    `[code_location, "dlt", "focus", table_name]`
  - `build_focus_dlt_assets()` factory -- for each table in config, creates a
    `dlt_assets` definition using:
    - `sql_table` standalone resource from `dlt.sources.sql_database`
    - `reflection_level="full_with_precision"` (no custom type/nullability
      adapters)
    - `backend="pyarrow"`
    - `defer_table_reflect=True`
    - `write_disposition="replace"` (daily full replace)
    - BigQuery destination with `autodetect_schema=True`
    - Dataset: `dagster_kippmiami_dlt_focus`
    - Pool: `dlt_focus_kippmiami` (limits concurrent connections)
  - No custom callbacks unless Focus testing reveals Postgres-specific issues.
    Start clean.
- `CLAUDE.md` -- documents the factory, IP allowlist constraint, connection
  pattern

**Code location: `src/teamster/code_locations/kippmiami/dlt/focus/`**

- `assets.py` -- loops over YAML config, calls factory per table
- `config/focus.yaml` -- flat table list (Focus uses `public` schema), format:

  ```yaml
  assets:
    - table_name: students
    - table_name: student_enrollment
      op_tags:
        dagster/priority: "1"
  ```

- `schedules.py` -- single daily `ScheduleDefinition` targeting all Focus assets

**Connection**: `ConnectionStringCredentials` assembled from individual env vars
(`FOCUS_DB_DRIVERNAME`, `FOCUS_DB_HOST`, `FOCUS_DB_DATABASE`,
`FOCUS_DB_USERNAME`, `FOCUS_DB_PASSWORD`, `FOCUS_DB_PORT`), following the
Illuminate pattern.

### dbt: new `focus` source-system project

**New project: `src/dbt/focus/`**

Following the existing source-system project pattern (like `powerschool`,
`deanslist`):

- `dbt_project.yml` -- project name `focus`, standard variable defaults
  (`current_academic_year`, `current_fiscal_year`, `local_timezone`)
- `profiles.yml` -- Dagster-only profile (default target `prod` + `defer`)
- `packages.yml` -- `dbt_utils`
- `CLAUDE.md`

**Source definition**: `models/staging/sources-bigquery.yml`

- Source name: `focus`
- Schema: `dagster_kippmiami_dlt_focus` (hardcoded -- BQ-native, not external)
- Each table with
  `meta.dagster.asset_key: ["kippmiami", "dlt", "focus", "<table_name>"]` for
  Dagster lineage

**Staging models** -- one per source table, `stg_focus__<table_name>.sql`:

- `contract: enforced: true` (set at directory level in `dbt_project.yml`)
- Uniqueness test on PK
- Column renames for clarity (boolean `is_` prefixes, reserved word quoting)
- Soft-delete filters where applicable
- Description on model and every column

**Intermediate models** -- domain-specific joins:

- `int_focus__student_enrollment` -- joins enrollment + schools + grade levels +
  codes
- `int_focus__attendance_day` -- joins attendance_day + codes + marking_periods
- `int_focus__attendance_period` -- joins attendance_period + course_periods +
  school_periods
- `int_focus__schedule` -- joins schedule + course_periods + courses +
  marking_periods
- `int_focus__gradebook_grades` -- joins gradebook_grades + assignments +
  assignment_types
- `int_focus__report_card_grades` -- joins student_report_card_grades +
  report_card_grades + scales
- Others as needed based on actual data exploration

### dbt: kippmiami + kipptaf integration

**kippmiami**:

- Add `focus` as a local package in `kippmiami/packages.yml`
- Focus staging/intermediate models available as refs within kippmiami

**kipptaf**:

- `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` -- source pointing to
  kippmiami's Focus dataset, using the region schema pattern (dev-only prefix)
- Staging models in kipptaf to re-expose kippmiami Focus models for downstream
  mart consumption (e.g., `stg_kippmiami__focus__students`,
  `stg_kippmiami__focus__student_enrollment`)
- Follows kipptaf's existing pattern for consuming district sources

This keeps the door open for future districts adopting Focus.

### Dagster wiring

**Code location `kippmiami`**:

- `dlt/focus/` module added
- `definitions.py` updated: import focus module, add assets via
  `load_assets_from_modules()`, add schedule, add credential resource

**Schedule**:

- Name: `kippmiami__dlt__focus__daily_asset_job_schedule`
- Cron: `0 0 * * *` (midnight ET)
- Timezone: `America/New_York`
- Targets all Focus dlt assets
- Can be split into multiple schedules later if different cadences are needed

**dbt automation**: No separate dbt schedule changes -- kippmiami's existing
`AutomationConditionSensor` picks up new Focus staging/intermediate models when
upstream dlt assets materialize.

### Infrastructure

**In-repo changes**:

1. New `OnePasswordItem` in `.k8s/1password/items.yaml`:

   ```yaml
   apiVersion: onepassword.com/v1
   kind: OnePasswordItem
   metadata:
     name: op-focus-db-kippmiami
     namespace: dagster-cloud
   spec:
     itemPath: vaults/Data Team/items/Focus DB - Miami
   ```

2. Focus DB env vars added to `kippmiami/dagster-cloud.yaml` in both
   `server_k8s_config` and `run_k8s_config` env lists:
   - `FOCUS_DB_DRIVERNAME` (key: `drivername`)
   - `FOCUS_DB_HOST` (key: `host`)
   - `FOCUS_DB_DATABASE` (key: `database`)
   - `FOCUS_DB_USERNAME` (key: `username`)
   - `FOCUS_DB_PASSWORD` (key: `password`)
   - `FOCUS_DB_PORT` (key: `port`)

   All sourced from `op-focus-db-kippmiami` secret.

**Manual (outside repo)**:

1. Focus Postgres credentials created in 1Password `Data Team` vault as "Focus
   DB - Miami"
2. Cloud NAT rule in GCP for static IP egress to Focus's Postgres host
3. Focus's IP allowlist updated to include the GKE static IP

### Testing constraints

Focus uses an IP allowlist. Local codespace development cannot reach the
database. Connection verification and data testing must happen via branch
deployments (same constraint as Illuminate). The dlt library code can be
validated structurally (imports, config parsing) but end-to-end testing requires
a deployed environment with network access.

## Key design decisions

1. **dlt over Airbyte** -- the team is moving away from Airbyte (Illuminate was
   migrated). dlt gives full control, no external service cost, and aligns with
   the architectural direction.

2. **`sql_table` over `sql_database`** -- dlt 1.24.0's standalone `sql_table`
   resource is more granular than wrapping `sql_database` with a single-table
   list. Supports per-table `write_disposition`, `primary_key`, `merge_key`, and
   `incremental` config. Cleaner pattern that can be backported to Illuminate.

3. **`full_with_precision` reflection** -- captures precision/scale natively
   instead of using custom type adapters like Illuminate's
   `unbounded_numeric_adapter`. Reduces custom code.

4. **No custom callbacks initially** -- start clean, add only if Focus testing
   reveals Postgres-specific issues (e.g., infinity dates, exotic types).

5. **Daily full-replace** -- simplest starting point. Cadence can be split later
   once Focus data volumes and change patterns are understood.

6. **Separate `focus` dbt project** -- follows the source-system project
   pattern, not merged into kippmiami. Allows future districts to adopt Focus by
   consuming it as a package.

7. **kipptaf exposure** -- Focus models are surfaced to kipptaf via regional
   sources, same as other district data. Keeps the cross-SIS mart as a separate
   future project.

## File inventory

### New files

```text
src/teamster/libraries/dlt/focus/
  __init__.py
  assets.py
  CLAUDE.md

src/teamster/code_locations/kippmiami/dlt/
  __init__.py
  focus/
    __init__.py
    assets.py
    schedules.py
    config/
      focus.yaml

src/dbt/focus/
  dbt_project.yml
  profiles.yml
  packages.yml
  CLAUDE.md
  models/
    staging/
      sources-bigquery.yml
      stg_focus__<table>.sql + .yml  (one per Phase 1 table, ~60)
    intermediate/
      int_focus__student_enrollment.sql + .yml
      int_focus__attendance_day.sql + .yml
      int_focus__attendance_period.sql + .yml
      int_focus__schedule.sql + .yml
      int_focus__gradebook_grades.sql + .yml
      int_focus__report_card_grades.sql + .yml
      (others as needed)

src/dbt/kipptaf/models/focus/
  sources-kippmiami.yml
  stg_kippmiami__focus__*.sql + .yml  (wrappers for mart consumption)
```

### Modified files

```text
.k8s/1password/items.yaml                              -- new OnePasswordItem
src/teamster/code_locations/kippmiami/dagster-cloud.yaml  -- Focus DB env vars
src/teamster/code_locations/kippmiami/definitions.py      -- import + wire focus
src/dbt/kippmiami/packages.yml                            -- add focus package
src/dbt/kippmiami/dbt_project.yml                         -- focus var overrides (if needed)
```

## ERD reference

The Focus database ERD is documented in `Focus DB Diagram.pdf` at the project
root. It covers 19 domain areas with Crow's Foot notation showing table
relationships. The Phase 1 domains listed above are pages 3-18 and 21-22 of that
document.
