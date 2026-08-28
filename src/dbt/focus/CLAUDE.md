# CLAUDE.md — `dbt/focus/`

Source-system staging project for **Focus SIS** data (PostgreSQL). Provides the
BigQuery source definitions for Focus dlt loads, consumed by district-specific
dbt projects (currently `kippmiami`).

## Schema reference

Full Focus DB ERD reference: `docs/superpowers/specs/references/focus-db-erd.md`
— table groups, PK/FK join keys, custom-field storage, and the
`attendance_calendar` (per-day school dates) vs `attendance_calendars` (calendar
headers) distinction. First day of school = `min(school_date)` per `syear` over
`default_calendar = 'Y'` calendars (`int_focus__school_year_first_day` — lives
in this package; kipptaf's copy of the same name is a thin passthrough
`source()`-ing this package's built output, not a re-derivation).

The kipptaf `rpt_focus__*` SFTP extracts keep a `trunk-ignore(sqlfluff/ST06)` —
the Focus import column order is contract-fixed. ST06 firing is
expression-shape-dependent, so keep the ignore even when a diff makes it look
vestigial.

## Data Flow

Focus Postgres → dlt `sql_database` → BigQuery (`dagster_<project>_dlt_focus`) →
dbt staging models → dbt intermediate models

## Focus field value codes

A Focus custom field's allowed value codes live in
`dagster_<district>_dlt_focus.custom_fields` (find the field by `title` /
`column_name`) joined to `custom_field_select_options` on
`custom_field_select_options.source_id = custom_fields.id` — `code` is the value
Focus expects, `label` is the human name. The join is `source_id` only — also
filter `custom_field_select_options.source_class = 'CustomField'` (or
`'CustomFieldLogColumn'` for log-column slots) so the shared `source_id` space
doesn't collide across owner types. `source_class` on the options table is the
owner-type literal, never the entity class (`SISSchool`, etc.); matching the
entity class returns zero rows. To DECODE a stored value: the entity stores the
select-option `id` (`custom_field_select_options.id`) for some fields and the
`code` (e.g. `prior_state`=`FL`) for others, so match the stored value against
BOTH `id` and `code`, then read `label`. Verify by spot-checking decoded values
— a wrong match key returns all-null labels but still passes build, grain, and
lint. (`code` also drives Finalsite→Focus import crosswalks.)

**Custom-field storage.** Values live inline on the entity table's wide
`custom_NNN` columns (e.g. `students.custom_100000105`), NOT in `custom_fields`
— that is the _definition_ catalog. Join definition→entity column on
`custom_fields.column_name` + `source_class`. `title` is the readable name (slug
it for the staging alias); `select`/`multiple` values are stored option `id`s or
`code`s (varies by field; decode to `label` via the crosswalk above); `log`-type
values live in `custom_field_log_entries`; `computed`/`holder` are not stored.
Custom fields are NOT always named `custom_NNN` — some use semantic
`column_name`s (e.g. `users.birth_date`, `charter_*`); when profiling an
entity's populated custom fields, scan the FULL table and join the whole catalog
on `lower(column_name)`, since filtering to `custom_*`-prefixed columns silently
misses the semantic-named ones.

**The `__pivot` models now decode every populated field that has select
options** (all 92, per #4597 — previously 32, all `custom_*`-prefixed).
Semantic-named fields are covered too. Two exclusions are deliberate:
`users.custom_l790` and `users.custom_l1472` are option_query-backed, so the
catalog holds zero `custom_field_select_options` rows and there is nothing to
decode. When adding a field to a pivot, check that it has options first — a
field with none yields an all-null label column that still builds and lints
clean.

**An all-null label column has two innocent causes besides a wrong match key.**
The field has no `custom_field_select_options` rows at all (option_query-backed,
above), or every stored value points at a **soft-deleted** option —
`stg_focus__custom_field_select_options` filters `where deleted is null`, so a
deleted option contributes no label (`students.custom_1429` is the live
example). Check both before assuming the `option_id`/`code` match is broken.

**A decode can be an identity mapping.** `master_courses.course_level`'s options
are `1`→`1`, `2`→`2`, `3`→`3`, so `course_level_label` repeats the stored code.
Before treating a decode as valuable, check `label` against `code`.

**Population is not informativeness.** Most Focus Florida-reporting fields are
non-null on every row but hold a single default value, so a
`countif(... is not null)` scan overstates the value of decoding them. Add
`count(distinct <stored value>)` when profiling.

`source_class`→entity-table map (use the catalog's own spelling, NOT the
entity's): `SISStudent`→students, `FocusUser`→users, `SISSchool`→schools,
`StudentEnrollment`→student_enrollment, `CoursePeriod`→course_periods,
`CourseCatalog`→master_courses, `Course`→courses.

**Two join gotchas, each silently returns zero matches.** (1) `column_name` is
UPPERCASE in the catalog (`CUSTOM_FIELD_3`, `CUSTOM_2`) but lowercase on the
entity table (`custom_field_3`) — join on `lower(column_name)`. (2) Use the
catalog `source_class` spelling — e.g. enrollment fields are under
`StudentEnrollment`, not `SISStudentEnrollment`. With both handled, the
`course_periods`, `master_courses`, `courses`, and `student_enrollment`
positional `custom_N` / `custom_field_N` slots DO resolve to catalog titles
(e.g. `master_courses.custom_field_3` = "Core for Class Size",
`course_periods.custom_4` = "Scheduling Method"). Genuinely unlabeled (no
catalog row): `course_subjects` (no `CourseSubject` class) and
`master_courses.custom_field_11`.

## Identifier spaces

**Three distinct school identifier spaces.** Focus `schools.id` is an internal
integer (14, 15, 58...); `school_number` is a Florida school code (`2008A`); the
network id is `powerschool_school_id`, reachable only via
`stg_google_sheets__people__locations.focus_school_id`. Joining the wrong one
null-fills every school attribute with no error.

**Same column name, different concept.** Focus `fteid` holds a Florida education
identifier string (`FL000007024992`); the network `fteid` is a PowerSchool
numeric id. Casting fails outright and `safe_cast` would null real data under a
misleading heading — drop such columns and let the consuming union null-fill.

The student id has the same shape of trap: `students.student_id` is the network
student number prefixed with `8400` (Miami-Dade's FLDOE district number), and
`int_focus__student_enrollment_roster.student_number` holds that PREFIXED form
despite its name, so joining on it by name returns zero matches with no error.

## Source data conventions

**Soft-delete.** Focus `deleted INT64` is `NULL` for live rows and `1` for
deleted — **never `0`**. Filter `where deleted is null` in staging (`= 0`
matches nothing) and omit the column. Present on `students`, `users`, `schools`,
`address`, `student_enrollment_codes`, the `custom_field*` tables; absent on
others (e.g. `custom_field_log_entries`). `inactive`/`active`/`archived` are raw
attributes, not delete sentinels.

**Primary keys.** Most tables PK on `id`; some on `<entity>_id` (`address_id`,
`course_id`, `course_period_id`, `marking_period_id`, `period_id`,
students→`student_id`, users→`staff_id` (`profile_id` is null for nearly all
rows).

## Model Structure

```text
models/
  staging/
    sources-bigquery.yml          # BQ-native sources (dlt-loaded, not external)
    stg_focus__<table>.sql        # one contract-enforced model per source table
    properties/
      stg_focus__<table>.yml      # contract columns, tests, descriptions
```

Staging models are contract-enforced (`contract: enforced: true`, set at the
`staging` directory level in `dbt_project.yml`): every projected column is
declared with a `data_type` in `properties/`, with a `unique` + `not_null` PK
test at `severity: error`. Each model selects from a
`{{ source("focus", ...) }}` relation, drops dlt bookkeeping (`_dlt_*`) and the
audit-quad, and applies the soft-delete filter where the table has one. Data
comes from dlt (not external tables), so sources use `sources-bigquery.yml` with
a plain schema var. Intermediate (`int_focus__*`) models layer on top.

## Key Variables

| Variable                | Default                            | Notes                           |
| ----------------------- | ---------------------------------- | ------------------------------- |
| `focus_schema`          | `dagster_<project_name>_dlt_focus` | BQ dataset with dlt-loaded data |
| `current_academic_year` | `0`                                | Overridden per district         |
| `current_fiscal_year`   | `0`                                | Overridden per district         |
| `local_timezone`        | `UTC`                              | Overridden per district         |

## Cross-Project Usage

This project is never run standalone in production. District projects reference
it as a dbt package and override variables. `{{ project_name }}` in source
definitions resolves to the consuming district project name, enabling correct
Dagster asset key lineage.

To add a NEW kipptaf dependency on Focus data in a single PR, declare the dlt
landing dataset (`dagster_kippmiami_dlt_focus`) as a BQ-native
`sources-bigquery.yml` source (hardcoded schema, no target branch) — it reads
prod in all targets, so kipptaf CI resolves it without seeding `zz_stg`. Only
the raw dlt tables exist in prod pre-merge; district `stg_focus__*` do not.

This package declares only `dbt_utils` in its own `packages.yml` — models here
must not reference macros from another source-system package (e.g.
`finalsite.clean_phone`), since packages are not necessarily installed together
and a consuming district project may lack it. Phone values are therefore emitted
raw, as stored in Focus; normalization (E.164) is applied by the downstream
consumer, not in this package.
