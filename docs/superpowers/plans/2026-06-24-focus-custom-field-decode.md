# Focus Custom-Field Decode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decode Focus SIS `select` / `multiple` custom-field codes to labels
and reshape the `log`-type fields into a long model, as additive `int_focus__*`
intermediate models.

**Architecture:** A shared `int_focus__custom_field_options` crosswalk resolves
codes to labels. One `int_focus__<entity>__pivot` per entity decodes that
entity's `select` (and, for users, `multiple`) fields via UNPIVOT → join
crosswalk → PIVOT, emitting labels-only keyed by the entity PK.
`int_focus__custom_field_log__unpivot` reshapes the two populated log fields
wide→long. No staging changes; codes stay in staging and consumers join
staging + pivot on the PK.

**Tech Stack:** dbt (BigQuery dialect), the `focus` source-system dbt package
built inside the `kippmiami` district project, `dbt_utils`. Source data in
`dagster_kippmiami_dlt_focus`.

## Global Constraints

Every task's requirements implicitly include this section. Values are verbatim
from the design spec
(`docs/superpowers/specs/2026-06-24-focus-custom-field-decode-design.md`).

- **No staging changes.** All new files live under
  `src/dbt/focus/models/intermediate/`. The `stg_focus__*` models and their
  contracts are not touched.
- **Decode join.** What the entity stores varies by field: the select-option
  **id** (e.g. `sex` → `2789`) for some, the **`code`** (e.g. `prior_state` →
  `FL`) for others. So each pivot matches its stored value against **either**:
  `unpivoted.stored_value in (options.option_id, options.code)`, filtered by
  `(source_class, column_name)`. The crosswalk exposes both
  `option_id = cast(select_options.id as string)` and `code`, built by joining
  `select_options.source_id = custom_fields.id` **with**
  `select_options.source_class = 'CustomField'` (never the entity class). Decode
  returns `label`.
- **Storage formats.** `select` = a single stored value (an option id like
  `5538`, or a code like `FL` — varies by field; cast to string for the
  unpivot). `multiple` = JSON-array string of those values (`["2795"]`) — parse
  with `json_value_array`, explode, match each to its label, re-aggregate to
  `array<string>`. The only in-scope `multiple` field is `users.education`.
- **`column_name` join keys.** The catalog stores `column_name` UPPERCASE
  (`CUSTOM_FIELD_3`); the crosswalk lowercases it. All decode joins use
  lowercase literals (e.g. `'custom_100000004'`), which grep back to the staging
  alias.
- **Labels-only.** Each `__pivot` model emits the entity PK + `<slug>_label`
  columns (and `education_label array<string>` for users). No code columns;
  codes remain in staging.
- **Naming.** Decode-to-wide models = `int_focus__<entity>__pivot`; the
  wide-to-long log model = `int_focus__custom_field_log__unpivot`; the crosswalk
  = `int_focus__custom_field_options`.
- **Tests.** Every intermediate model needs a uniqueness test (repo convention).
  Crosswalk grain `option_id` (`unique` at `severity: error`). Each pivot: PK
  `unique` + `not_null`. Log: `unique_combination_of_columns` on
  `(log_entry_id, slot_column_name)`.
- **Descriptions.** Every new model and every column needs a `description:` in
  `properties/`.
- **PII.** Person-keyed models (`students`, `student_enrollment`, `users`, log)
  carry `config.meta.contains_pii: true`. Tag sensitive decoded columns
  (`sex_label`, `race_*_label`, `language_label`) at the column level too
  (FERPA-aligned broad stance, pending People Operations confirmation). School-
  and course-domain models are not PII.
- **`option_query` exclusion.** `users.profile_on_non_production_sites`
  (`custom_l790`) is `option_query`-backed and is **not** decoded (skipped as
  low-value); its code stays in staging.
- **SQL style** (`.trunk/config/.sqlfluff`): BigQuery, trailing commas in
  `SELECT`, single quotes, max line length 88, ST06 column ordering, no
  `GROUP BY ALL`, no `ORDER BY` in models. Reserved words backtick-quoted.
- **dbt execution** (run from the worktree; never `--target prod`):

  ```bash
  # one-time setup
  wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-custom-field-decode
  uv run dbt deps --project-dir "$wt/src/dbt/kippmiami"
  # refresh the prod manifest if stale (post-merge hook usually keeps it fresh):
  uv run dbt parse --target prod --project-dir src/dbt/kippmiami --target-path target/prod

  # build/test a model against real data (prod staging via --defer; writes to your dev schema):
  dbtb () { uv run dbt build --select "$1" \
    --project-dir "$wt/src/dbt/kippmiami" \
    --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod \
    --target dev ; }
  ```

  `DBT_PROFILES_DIR` must point at the repo `.dbt` (developer profile + ADC).
  Build Task 1 (crosswalk) first — later models pick it up from your dev schema
  via `--defer`.

- **Lint** (per file, from inside the worktree):

  ```bash
  cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force <files>
  ```

- **Commit** (lowercase shell vars only — uppercase trips the secret hook):

  ```bash
  git -C "$wt" add <files>
  git -C "$wt" commit -m "<type>(dbt): <subject>" -m "Refs #4258" \
    -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## File Structure

All under `src/dbt/focus/models/intermediate/` (and its `properties/`):

| File                                                      | Responsibility                                   |
| --------------------------------------------------------- | ------------------------------------------------ |
| `int_focus__custom_field_options.sql` + yml               | Code→label crosswalk (table)                     |
| `int_focus__students__pivot.sql` + yml                    | Decode 9 SISStudent selects                      |
| `int_focus__schools__pivot.sql` + yml                     | Decode 3 SISSchool selects                       |
| `int_focus__student_enrollment__pivot.sql` + yml          | Decode 5 StudentEnrollment selects               |
| `int_focus__users__pivot.sql` + yml                       | Decode 1 FocusUser select + `education` multiple |
| `int_focus__course_periods__pivot.sql` + yml              | Decode 9 CoursePeriod selects                    |
| `int_focus__master_courses__pivot.sql` + yml              | Decode 3 CourseCatalog selects                   |
| `int_focus__courses__pivot.sql` + yml                     | Decode 2 Course selects                          |
| `int_focus__custom_field_log__unpivot.sql` + yml          | Wide→long reshape of 2 log fields                |
| `tests/test_focus__custom_field_options_known_fields.sql` | Guard: corrected join resolves known fields      |

The existing `int_focus__student_enrollment.sql` (title enrichment) is **not**
touched.

---

## Task 1: Crosswalk `int_focus__custom_field_options`

**Files:**

- Create:
  `src/dbt/focus/models/intermediate/int_focus__custom_field_options.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__custom_field_options.yml`
- Create:
  `src/dbt/focus/tests/test_focus__custom_field_options_known_fields.sql`
- Modify: `src/dbt/focus/CLAUDE.md` (clarify the decode join)

**Interfaces:**

- Consumes: `stg_focus__custom_fields` (`id`, `source_class`, `column_name`),
  `stg_focus__custom_field_select_options` (`source_id`, `source_class`, `code`,
  `label`).
- Produces: a table with columns `option_id string` (the select-option id),
  `source_class string`, `column_name string` (lowercased), `code string`,
  `label string`. Grain `option_id` (globally unique). Consumed by every
  `__pivot` model, which matches its stored value against `option_id` OR `code`
  (storage varies by field).

- [ ] **Step 1: Write the failing guard test**

`src/dbt/focus/tests/test_focus__custom_field_options_known_fields.sql`:

```sql
-- Guards the corrected decode join: known in-scope fields must resolve to
-- options. Returns offending (source_class, column_name) rows -> any row fails.
with expected as (
    select 'SISSchool' as source_class, 'custom_100000004' as column_name
    union all
    select 'SISStudent', 'custom_200000000'
    union all
    select 'StudentEnrollment', 'custom_4'
)
select expected.source_class, expected.column_name
from expected
left join {{ ref("int_focus__custom_field_options") }} as o
    on o.source_class = expected.source_class
    and o.column_name = expected.column_name
where o.option_id is null
```

- [ ] **Step 2: Run it to verify it fails**

Run: `dbtb int_focus__custom_field_options` Expected: FAIL at parse/compile —
`int_focus__custom_field_options` does not exist yet.

- [ ] **Step 3: Write the crosswalk model**

`src/dbt/focus/models/intermediate/int_focus__custom_field_options.sql`:

```sql
with
    cf as (
        select
            id,
            source_class,
            lower(column_name) as column_name,
        from {{ ref("stg_focus__custom_fields") }}
    ),

    opt as (
        select
            cast(id as string) as option_id,
            source_id,
            code,
            label,
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomField'  -- owner-type filter; keep inactive
    )

select
    opt.option_id,
    cf.source_class,
    cf.column_name,
    opt.code,
    opt.label,
from opt
inner join cf on opt.source_id = cf.id
```

- [ ] **Step 4: Write the properties yml**

`src/dbt/focus/models/intermediate/properties/int_focus__custom_field_options.yml`:

```yaml
models:
  - name: int_focus__custom_field_options
    description: >-
      Crosswalk for Focus select/multiple custom fields, keyed by option_id (the
      value the entity stores). Joins the custom-field catalog to its stored
      select options on select_options.source_id = custom_fields.id with
      source_class 'CustomField' (the owner-type literal, never the entity
      class). One row per option; inactive options are retained so historical
      stored ids still decode. label is the human name; code is the Focus
      import/export value.
    config:
      materialized: table
    columns:
      - name: option_id
        description: >-
          Stored select-option id — the value persisted on the entity record and
          the decode join key.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: source_class
        description: Owning entity class of the custom field (e.g. SISStudent).
        data_tests:
          - not_null:
              config:
                severity: error
      - name: column_name
        description:
          Lowercased catalog column_name of the field (e.g. custom_100000004).
        data_tests:
          - not_null:
              config:
                severity: error
      - name: code
        description:
          Focus import/export code for the option (not the stored value).
      - name: label
        description: Human-readable label for the option.
```

- [ ] **Step 5: Clarify the decode join in `src/dbt/focus/CLAUDE.md`**

In the "Focus field value codes" section, after the sentence ending "`label` is
the human name.", add:

```text
The join is `source_id` only — also filter `custom_field_select_options.source_class = 'CustomField'` (or `'CustomFieldLogColumn'` for log-column slots) so the shared `source_id` space doesn't collide across owner types. `source_class` on the options table is the owner-type literal, never the entity class (`SISSchool`, etc.); matching the entity class returns zero rows. To DECODE a stored entity value: the entity stores the select-option `id` (`custom_field_select_options.id`), NOT its `code` — join the stored value to `id` and read `label`. (`code` is the Focus import/export value, used for the Finalsite→Focus direction.)
```

- [ ] **Step 6: Build and run tests against real data**

Run: `dbtb int_focus__custom_field_options` Expected: PASS — model builds; the
`unique` test on `option_id` and the `known_fields` guard pass. `option_id` is
the select-option PK (globally unique, non-null), so no dedupe is needed.

- [ ] **Step 7: Spot-check decode correctness**

Run via BigQuery MCP (`mcp__bigquery__execute_sql`), substituting your dev
schema:

```sql
select option_id, code, label
from `teamster-332318`.<your_dev_schema>.int_focus__custom_field_options
where source_class = 'SISSchool' and column_name = 'custom_100000004'
order by option_id
```

Expected: 5 rows mapping `option_id` (e.g. `5538`) → `label` (`E - Elementary`).

- [ ] **Step 8: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__custom_field_options.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__custom_field_options.yml \
  src/dbt/focus/tests/test_focus__custom_field_options_known_fields.sql \
  src/dbt/focus/CLAUDE.md
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__custom_field_options.sql src/dbt/focus/models/intermediate/properties/int_focus__custom_field_options.yml src/dbt/focus/tests/test_focus__custom_field_options_known_fields.sql src/dbt/focus/CLAUDE.md
git -C "$wt" commit -m "feat(dbt): add Focus custom-field code-to-label crosswalk" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `int_focus__students__pivot`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__students__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__students` (`student_id` + the 9 select slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per `student_id` with 9 `<slug>_label` columns. PK
  `student_id`.

Decode map (`source_class = 'SISStudent'`):
`ethnicity_hispanic_or_latino`→`custom_100000105`,
`race_white`→`custom_100000104`,
`race_black_or_african_american`→`custom_100000102`,
`race_asian`→`custom_100000101`, `sex`→`custom_200000000`,
`race_american_indian_or_alaska_native`→`custom_100000100`,
`race_native_hawaiian_or_other_pacific_islander`→`custom_100000103`,
`residence_county`→`custom_837`, `language`→`custom_200000005`.

- [ ] **Step 1: Write the model**

`src/dbt/focus/models/intermediate/int_focus__students__pivot.sql`:

```sql
with
    encoded as (
        select
            student_id,
            cast(ethnicity_hispanic_or_latino as string) as custom_100000105,
            cast(race_white as string) as custom_100000104,
            cast(race_black_or_african_american as string) as custom_100000102,
            cast(race_asian as string) as custom_100000101,
            cast(sex as string) as custom_200000000,
            cast(race_american_indian_or_alaska_native as string)
                as custom_100000100,
            cast(race_native_hawaiian_or_other_pacific_islander as string)
                as custom_100000103,
            cast(residence_county as string) as custom_837,
            cast(`language` as string) as custom_200000005,
        from {{ ref("stg_focus__students") }}
    ),

    unpivoted as (
        select student_id, column_name, stored_value
        from encoded unpivot (
            stored_value for column_name in (
                custom_100000105,
                custom_100000104,
                custom_100000102,
                custom_100000101,
                custom_200000000,
                custom_100000100,
                custom_100000103,
                custom_837,
                custom_200000005
            )
        )
    ),

    decoded as (
        select
            unpivoted.student_id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'SISStudent'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_100000105' as ethnicity_hispanic_or_latino_label,
        'custom_100000104' as race_white_label,
        'custom_100000102' as race_black_or_african_american_label,
        'custom_100000101' as race_asian_label,
        'custom_200000000' as sex_label,
        'custom_100000100' as race_american_indian_or_alaska_native_label,
        'custom_100000103' as race_native_hawaiian_or_other_pacific_islander_label,
        'custom_837' as residence_county_label,
        'custom_200000005' as language_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

`src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml`:

```yaml
models:
  - name: int_focus__students__pivot
    description: >-
      Decoded labels for the SISStudent select custom fields, one row per
      student_id. Join to stg_focus__students on student_id for the codes. A
      null label means the student had no code for that field.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_id
        description: Primary key — Focus local student id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: ethnicity_hispanic_or_latino_label
        description:
          Decoded label for the ethnicity_hispanic_or_latino select field.
        config:
          meta:
            contains_pii: true
      - name: race_white_label
        description: Decoded label for the race_white select field.
        config:
          meta:
            contains_pii: true
      - name: race_black_or_african_american_label
        description:
          Decoded label for the race_black_or_african_american select field.
        config:
          meta:
            contains_pii: true
      - name: race_asian_label
        description: Decoded label for the race_asian select field.
        config:
          meta:
            contains_pii: true
      - name: sex_label
        description: Decoded label for the sex select field.
        config:
          meta:
            contains_pii: true
      - name: race_american_indian_or_alaska_native_label
        description:
          Decoded label for the race_american_indian_or_alaska_native field.
        config:
          meta:
            contains_pii: true
      - name: race_native_hawaiian_or_other_pacific_islander_label
        description:
          Decoded label for the race_native_hawaiian_or_other_pacific_islander
          field.
        config:
          meta:
            contains_pii: true
      - name: residence_county_label
        description: Decoded label for the residence_county select field.
        config:
          meta:
            contains_pii: true
      - name: language_label
        description: Decoded label for the language select field.
        config:
          meta:
            contains_pii: true
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__students__pivot` Expected: PASS — builds; `unique` +
`not_null` on `student_id` pass.

- [ ] **Step 4: Spot-check**

```sql
select count(*) as n, countif(sex_label is not null) as n_sex_label
from `teamster-332318`.<your_dev_schema>.int_focus__students__pivot
```

Expected: `n_sex_label` > 0 and labels look human-readable (join a few rows back
to `stg_focus__students.sex` to confirm code→label).

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__students__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__students__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__students__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode SISStudent custom fields in int_focus__students__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `int_focus__schools__pivot`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__schools__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__schools__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__schools` (PK `id` + slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per `id` with 3 `<slug>_label` columns. PK `id`. Not PII.

Decode map (`source_class = 'SISSchool'`): `school_level`→`custom_100000004`,
`school_type`→`custom_200000326`, `technical_center`→`custom_50000002`.

- [ ] **Step 1: Write the model**

`src/dbt/focus/models/intermediate/int_focus__schools__pivot.sql`:

```sql
with
    encoded as (
        select
            id,
            cast(school_level as string) as custom_100000004,
            cast(school_type as string) as custom_200000326,
            cast(technical_center as string) as custom_50000002,
        from {{ ref("stg_focus__schools") }}
    ),

    unpivoted as (
        select id, column_name, stored_value
        from encoded unpivot (
            stored_value for column_name in (
                custom_100000004, custom_200000326, custom_50000002
            )
        )
    ),

    decoded as (
        select
            unpivoted.id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'SISSchool'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_100000004' as school_level_label,
        'custom_200000326' as school_type_label,
        'custom_50000002' as technical_center_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__schools__pivot
    description: >-
      Decoded labels for the SISSchool select custom fields, one row per Focus
      school id. Join to stg_focus__schools on id for the codes.
    columns:
      - name: id
        description: Primary key — Focus school id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_level_label
        description: Decoded label for the school_level select field.
      - name: school_type_label
        description: Decoded label for the school_type select field.
      - name: technical_center_label
        description: Decoded label for the technical_center select field.
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__schools__pivot` Expected: PASS.

- [ ] **Step 4: Spot-check**

```sql
select id, school_level_label, school_type_label
from `teamster-332318`.<your_dev_schema>.int_focus__schools__pivot
order by id
```

Expected: `school_level_label` values like `E - Elementary` / `H - High`.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__schools__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__schools__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__schools__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__schools__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode SISSchool custom fields in int_focus__schools__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `int_focus__student_enrollment__pivot`

**Files:**

- Create:
  `src/dbt/focus/models/intermediate/int_focus__student_enrollment__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__student_enrollment` (PK `id` + slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per enrollment `id` with 5 `<slug>_label` columns. PK `id`.
  PII (student-linked).

Decode map (`source_class = 'StudentEnrollment'`): `prior_district`→`custom_1`,
`prior_state`→`custom_2`, `prior_country`→`custom_3`,
`educational_choice`→`custom_4`, `student_offender_transfer`→`custom_6`.

- [ ] **Step 1: Write the model**

```sql
with
    encoded as (
        select
            id,
            cast(prior_district as string) as custom_1,
            cast(prior_state as string) as custom_2,
            cast(prior_country as string) as custom_3,
            cast(educational_choice as string) as custom_4,
            cast(student_offender_transfer as string) as custom_6,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    unpivoted as (
        select id, column_name, stored_value
        from encoded unpivot (
            stored_value for column_name in (
                custom_1, custom_2, custom_3, custom_4, custom_6
            )
        )
    ),

    decoded as (
        select
            unpivoted.id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'StudentEnrollment'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_1' as prior_district_label,
        'custom_2' as prior_state_label,
        'custom_3' as prior_country_label,
        'custom_4' as educational_choice_label,
        'custom_6' as student_offender_transfer_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__student_enrollment__pivot
    description: >-
      Decoded labels for the StudentEnrollment select custom fields, one row per
      Focus enrollment id. Join to stg_focus__student_enrollment on id for
      codes.
    config:
      meta:
        contains_pii: true
    columns:
      - name: id
        description: Primary key — Focus student enrollment id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: prior_district_label
        description: Decoded label for the prior_district select field.
      - name: prior_state_label
        description: Decoded label for the prior_state select field.
      - name: prior_country_label
        description: Decoded label for the prior_country select field.
      - name: educational_choice_label
        description: Decoded label for the educational_choice select field.
      - name: student_offender_transfer_label
        description:
          Decoded label for the student_offender_transfer select field.
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__student_enrollment__pivot` Expected: PASS.

- [ ] **Step 4: Spot-check**

```sql
select count(*) as n, countif(prior_state_label is not null) as n_state
from `teamster-332318`.<your_dev_schema>.int_focus__student_enrollment__pivot
```

Expected: `n_state` > 0 with readable state labels.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__student_enrollment__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__student_enrollment__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode StudentEnrollment custom fields in int_focus__student_enrollment__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `int_focus__users__pivot`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__users__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__users__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__users` (PK `staff_id`, `active`, `education`),
  `int_focus__custom_field_options`.
- Produces: one row per `staff_id` with `active_label string` and
  `education_label array<string>`. PK `staff_id`. PII (staff).
  `profile_on_non_production_sites` is intentionally not decoded.

Decode map (`source_class = 'FocusUser'`): `active`→`custom_319000004` (select),
`education`→`custom_2` (multiple, JSON-array string).

- [ ] **Step 1: Write the model**

```sql
with
    encoded as (
        select
            staff_id,
            cast(active as string) as custom_319000004,
        from {{ ref("stg_focus__users") }}
    ),

    unpivoted as (
        select staff_id, column_name, stored_value
        from encoded unpivot (stored_value for column_name in (custom_319000004))
    ),

    decoded as (
        select
            unpivoted.staff_id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'FocusUser'
    ),

    select_pivot as (
        select *
        from decoded pivot (
            any_value(label) for column_name in (
                'custom_319000004' as active_label
            )
        )
    ),

    -- multiple: education is a JSON array of option ids like '["2795"]'; explode,
    -- map each id to its label, re-aggregate. CTE form avoids a correlated subquery.
    education as (
        select
            users.staff_id,
            array_agg(options.label ignore nulls order by options.label)
                as education_label,
        from {{ ref("stg_focus__users") }} as users
        cross join unnest(json_value_array(users.education)) as element_id
        left join {{ ref("int_focus__custom_field_options") }} as options
            on element_id in (options.option_id, options.code)
            and options.column_name = 'custom_2'
            and options.source_class = 'FocusUser'
        group by users.staff_id
    )

select
    select_pivot.staff_id,
    select_pivot.active_label,
    education.education_label,
from select_pivot
left join education on select_pivot.staff_id = education.staff_id
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__users__pivot
    description: >-
      Decoded labels for the FocusUser custom fields, one row per staff_id. Join
      to stg_focus__users on staff_id for the codes.
      profile_on_non_production_sites is option_query-backed and intentionally
      not decoded (its code stays in staging).
    config:
      meta:
        contains_pii: true
    columns:
      - name: staff_id
        description: Primary key — Focus staff id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: active_label
        description: Decoded label for the active select field.
      - name: education_label
        description: >-
          Decoded labels for the education multiple-select field, as an array
          (the stored value is a JSON array of option codes).
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__users__pivot` Expected: PASS — `unique` + `not_null` on
`staff_id` pass.

- [ ] **Step 4: Spot-check the multiple decode**

```sql
select staff_id, active_label, education_label
from `teamster-332318`.<your_dev_schema>.int_focus__users__pivot
where array_length(education_label) > 0
limit 20
```

Expected: `education_label` holds readable labels (e.g. a degree name) for staff
whose `stg_focus__users.education` is populated; non-populated staff have an
empty/null array.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__users__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__users__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__users__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__users__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode FocusUser custom fields in int_focus__users__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `int_focus__course_periods__pivot`

**Files:**

- Create:
  `src/dbt/focus/models/intermediate/int_focus__course_periods__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__course_periods__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__course_periods` (PK `course_period_id` + slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per `course_period_id` with 9 `<slug>_label` columns. PK
  `course_period_id`. Not PII.

Decode map (`source_class = 'CoursePeriod'`): `fefp_number`→`custom_2`,
`scheduling_method`→`custom_4`, `facility_type`→`custom_6`,
`cert_licensure_qual_status`→`custom_28`, `highly_qualified`→`custom_5`,
`reading_intervention_component`→`custom_25`, `location_of_student`→`custom_33`,
`eoc_exam_term`→`custom_34`, `basic_skills_exam`→`custom_22`.

- [ ] **Step 1: Write the model**

```sql
with
    encoded as (
        select
            course_period_id,
            cast(fefp_number as string) as custom_2,
            cast(scheduling_method as string) as custom_4,
            cast(facility_type as string) as custom_6,
            cast(cert_licensure_qual_status as string) as custom_28,
            cast(highly_qualified as string) as custom_5,
            cast(reading_intervention_component as string) as custom_25,
            cast(location_of_student as string) as custom_33,
            cast(eoc_exam_term as string) as custom_34,
            cast(basic_skills_exam as string) as custom_22,
        from {{ ref("stg_focus__course_periods") }}
    ),

    unpivoted as (
        select course_period_id, column_name, stored_value
        from encoded unpivot (
            stored_value for column_name in (
                custom_2,
                custom_4,
                custom_6,
                custom_28,
                custom_5,
                custom_25,
                custom_33,
                custom_34,
                custom_22
            )
        )
    ),

    decoded as (
        select
            unpivoted.course_period_id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'CoursePeriod'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_2' as fefp_number_label,
        'custom_4' as scheduling_method_label,
        'custom_6' as facility_type_label,
        'custom_28' as cert_licensure_qual_status_label,
        'custom_5' as highly_qualified_label,
        'custom_25' as reading_intervention_component_label,
        'custom_33' as location_of_student_label,
        'custom_34' as eoc_exam_term_label,
        'custom_22' as basic_skills_exam_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__course_periods__pivot
    description: >-
      Decoded labels for the CoursePeriod select custom fields, one row per
      Focus course_period_id. Join to stg_focus__course_periods on
      course_period_id.
    columns:
      - name: course_period_id
        description: Primary key — Focus course period (section) id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: fefp_number_label
        description: Decoded label for the fefp_number select field.
      - name: scheduling_method_label
        description: Decoded label for the scheduling_method select field.
      - name: facility_type_label
        description: Decoded label for the facility_type select field.
      - name: cert_licensure_qual_status_label
        description:
          Decoded label for the cert_licensure_qual_status select field.
      - name: highly_qualified_label
        description: Decoded label for the highly_qualified select field.
      - name: reading_intervention_component_label
        description:
          Decoded label for the reading_intervention_component select field.
      - name: location_of_student_label
        description: Decoded label for the location_of_student select field.
      - name: eoc_exam_term_label
        description: Decoded label for the eoc_exam_term select field.
      - name: basic_skills_exam_label
        description: Decoded label for the basic_skills_exam select field.
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__course_periods__pivot` Expected: PASS.

- [ ] **Step 4: Spot-check**

```sql
select count(*) as n, countif(facility_type_label is not null) as n_facility
from `teamster-332318`.<your_dev_schema>.int_focus__course_periods__pivot
```

Expected: `n_facility` > 0 with readable labels.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__course_periods__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__course_periods__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__course_periods__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__course_periods__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode CoursePeriod custom fields in int_focus__course_periods__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `int_focus__master_courses__pivot`

**Files:**

- Create:
  `src/dbt/focus/models/intermediate/int_focus__master_courses__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__master_courses__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__master_courses` (PK `course_id` + slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per `course_id` with 3 `<slug>_label` columns. PK
  `course_id`. Not PII.

Decode map (`source_class = 'CourseCatalog'`): `fefp`→`custom_field_5`,
`course_flag_1`→`custom_field_6`, `dual_enrollment_indicator`→`custom_field_13`.

- [ ] **Step 1: Write the model**

```sql
with
    encoded as (
        select
            course_id,
            cast(fefp as string) as custom_field_5,
            cast(course_flag_1 as string) as custom_field_6,
            cast(dual_enrollment_indicator as string) as custom_field_13,
        from {{ ref("stg_focus__master_courses") }}
    ),

    unpivoted as (
        select course_id, column_name, stored_value
        from encoded unpivot (
            stored_value for column_name in (
                custom_field_5, custom_field_6, custom_field_13
            )
        )
    ),

    decoded as (
        select
            unpivoted.course_id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'CourseCatalog'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_field_5' as fefp_label,
        'custom_field_6' as course_flag_1_label,
        'custom_field_13' as dual_enrollment_indicator_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__master_courses__pivot
    description: >-
      Decoded labels for the CourseCatalog (master course) select custom fields,
      one row per Focus course_id. Join to stg_focus__master_courses on
      course_id.
    columns:
      - name: course_id
        description: Primary key — Focus master course id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: fefp_label
        description: Decoded label for the fefp select field.
      - name: course_flag_1_label
        description: Decoded label for the course_flag_1 select field.
      - name: dual_enrollment_indicator_label
        description:
          Decoded label for the dual_enrollment_indicator select field.
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__master_courses__pivot` Expected: PASS.

- [ ] **Step 4: Spot-check**

```sql
select count(*) as n, countif(fefp_label is not null) as n_fefp
from `teamster-332318`.<your_dev_schema>.int_focus__master_courses__pivot
```

Expected: `n_fefp` > 0 with readable labels.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__master_courses__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__master_courses__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__master_courses__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__master_courses__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode CourseCatalog custom fields in int_focus__master_courses__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `int_focus__courses__pivot`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__courses__pivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__courses__pivot.yml`

**Interfaces:**

- Consumes: `stg_focus__courses` (PK `course_id` + slugs below),
  `int_focus__custom_field_options`.
- Produces: one row per `course_id` with 2 `<slug>_label` columns. PK
  `course_id`. Not PII.

Decode map (`source_class = 'Course'`): `course_sequence`→`custom_4`,
`ocp`→`custom_3`.

- [ ] **Step 1: Write the model**

```sql
with
    encoded as (
        select
            course_id,
            cast(course_sequence as string) as custom_4,
            cast(ocp as string) as custom_3,
        from {{ ref("stg_focus__courses") }}
    ),

    unpivoted as (
        select course_id, column_name, stored_value
        from encoded unpivot (stored_value for column_name in (custom_4, custom_3))
    ),

    decoded as (
        select
            unpivoted.course_id,
            unpivoted.column_name,
            options.label,
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on unpivoted.column_name = options.column_name
            and unpivoted.stored_value in (options.option_id, options.code)
            and options.source_class = 'Course'
    )

select *
from decoded pivot (
    any_value(label) for column_name in (
        'custom_4' as course_sequence_label,
        'custom_3' as ocp_label
    )
)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__courses__pivot
    description: >-
      Decoded labels for the Course select custom fields, one row per Focus
      course_id. Join to stg_focus__courses on course_id for the codes.
    columns:
      - name: course_id
        description: Primary key — Focus course id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: course_sequence_label
        description: Decoded label for the course_sequence select field.
      - name: ocp_label
        description: Decoded label for the ocp select field.
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__courses__pivot` Expected: PASS.

- [ ] **Step 4: Spot-check**

```sql
select count(*) as n, countif(ocp_label is not null) as n_ocp
from `teamster-332318`.<your_dev_schema>.int_focus__courses__pivot
```

Expected: `n_ocp` > 0 with readable labels.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__courses__pivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__courses__pivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__courses__pivot.sql src/dbt/focus/models/intermediate/properties/int_focus__courses__pivot.yml
git -C "$wt" commit -m "feat(dbt): decode Course custom fields in int_focus__courses__pivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `int_focus__custom_field_log__unpivot`

**Files:**

- Create:
  `src/dbt/focus/models/intermediate/int_focus__custom_field_log__unpivot.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__custom_field_log__unpivot.yml`

**Interfaces:**

- Consumes: `stg_focus__custom_field_log_entries` (`id`, `source_id`,
  `school_id`, `field_id`, `syear`, `created_at`, `updated_at`,
  `log_field1`..`log_field30`), `stg_focus__custom_field_log_columns` (`id`,
  `field_id`, `column_name`, `type`, `title`, `sort_order`),
  `stg_focus__custom_fields` (`id`, `title`),
  `stg_focus__custom_field_select_options` (`source_class`, `source_id`, `code`,
  `label`).
- Produces: long rows, grain `(log_entry_id, slot_column_name)`. PII
  (student-linked).

Notes: log slots decode via `select_options` keyed on
`source_class = 'CustomFieldLogColumn'`,
`source_id = custom_field_log_columns.id`. `completed_at` is omitted (always
null). Catalog `column_name` is UPPERCASE (`LOG_FIELD1`); lowercase it to match
the entry column names. Unpivot all 30 slots; the inner join to `log_columns`
drops slots a field does not define.

- [ ] **Step 1: Write the model**

```sql
with
    entries as (
        select
            id as log_entry_id,
            source_id as student_id,
            school_id,
            field_id,
            syear,
            created_at,
            updated_at,
            cast(log_field1 as string) as log_field1,
            cast(log_field2 as string) as log_field2,
            cast(log_field3 as string) as log_field3,
            cast(log_field4 as string) as log_field4,
            cast(log_field5 as string) as log_field5,
            cast(log_field6 as string) as log_field6,
            cast(log_field7 as string) as log_field7,
            cast(log_field8 as string) as log_field8,
            cast(log_field9 as string) as log_field9,
            cast(log_field10 as string) as log_field10,
            cast(log_field11 as string) as log_field11,
            cast(log_field12 as string) as log_field12,
            cast(log_field13 as string) as log_field13,
            cast(log_field14 as string) as log_field14,
            cast(log_field15 as string) as log_field15,
            cast(log_field16 as string) as log_field16,
            cast(log_field17 as string) as log_field17,
            cast(log_field18 as string) as log_field18,
            cast(log_field19 as string) as log_field19,
            cast(log_field20 as string) as log_field20,
            cast(log_field21 as string) as log_field21,
            cast(log_field22 as string) as log_field22,
            cast(log_field23 as string) as log_field23,
            cast(log_field24 as string) as log_field24,
            cast(log_field25 as string) as log_field25,
            cast(log_field26 as string) as log_field26,
            cast(log_field27 as string) as log_field27,
            cast(log_field28 as string) as log_field28,
            cast(log_field29 as string) as log_field29,
            cast(log_field30 as string) as log_field30,
        from {{ ref("stg_focus__custom_field_log_entries") }}
    ),

    unpivoted as (
        select
            log_entry_id,
            student_id,
            school_id,
            field_id,
            syear,
            created_at,
            updated_at,
            slot_column_name,
            value,
        from entries unpivot (
            value for slot_column_name in (
                log_field1, log_field2, log_field3, log_field4, log_field5,
                log_field6, log_field7, log_field8, log_field9, log_field10,
                log_field11, log_field12, log_field13, log_field14, log_field15,
                log_field16, log_field17, log_field18, log_field19, log_field20,
                log_field21, log_field22, log_field23, log_field24, log_field25,
                log_field26, log_field27, log_field28, log_field29, log_field30
            )
        )
    ),

    columns_meta as (
        select
            id as log_column_id,
            field_id,
            lower(column_name) as slot_column_name,
            type as slot_type,
            title as slot_title,
            sort_order as slot_sort_order,
        from {{ ref("stg_focus__custom_field_log_columns") }}
    ),

    fields_meta as (
        select
            id as field_id,
            title as field_title,
        from {{ ref("stg_focus__custom_fields") }}
    ),

    options as (
        select
            cast(id as string) as option_id,
            source_id,
            code,
            label,
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomFieldLogColumn'
    )

select
    unpivoted.log_entry_id,
    unpivoted.student_id,
    unpivoted.school_id,
    unpivoted.field_id,
    columns_meta.log_column_id,
    columns_meta.slot_column_name,
    columns_meta.slot_type,
    columns_meta.slot_title,
    columns_meta.slot_sort_order,
    fields_meta.field_title,
    unpivoted.value,
    unpivoted.syear,
    unpivoted.created_at,
    unpivoted.updated_at,
    options.label as value_label,
from unpivoted
inner join columns_meta
    on unpivoted.field_id = columns_meta.field_id
    and unpivoted.slot_column_name = columns_meta.slot_column_name
left join fields_meta on unpivoted.field_id = fields_meta.field_id
left join options
    on columns_meta.log_column_id = options.source_id
    and unpivoted.value in (options.option_id, options.code)
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_focus__custom_field_log__unpivot
    description: >-
      Long reshape of Focus log-type custom fields. One row per log entry per
      populated slot: the entry keys, the slot's metadata (title/type/sort order
      from custom_field_log_columns), the stored value, and a decoded
      value_label for select-type slots. Currently covers the two populated
      student log fields (Immunization Compliance, ARMS Student Field Tracker).
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - log_entry_id
              - slot_column_name
          config:
            severity: error
    columns:
      - name: log_entry_id
        description: Focus custom_field_log_entries id.
      - name: student_id
        description: Owning student id (custom_field_log_entries.source_id).
      - name: school_id
        description: School id the log entry is attached to.
      - name: field_id
        description: Owning log custom field id (custom_fields.id).
      - name: log_column_id
        description: Log column id for the slot (custom_field_log_columns.id).
      - name: slot_column_name
        description: Lowercased slot storage column (log_fieldN).
      - name: slot_type
        description: Input type of the slot (select, checkbox, text, date).
      - name: slot_title
        description: Human-readable slot name from custom_field_log_columns.
      - name: slot_sort_order
        description: Display order of the slot within the field.
      - name: field_title
        description:
          Human-readable log field name (e.g. Immunization Compliance).
      - name: value
        description: Raw stored slot value.
      - name: syear
        description: Focus school year of the entry (populated for ARMS only).
      - name: created_at
        description: Log entry creation timestamp.
      - name: updated_at
        description: Log entry last-update timestamp.
      - name: value_label
        description: >-
          Decoded label for select-type slots; null for non-select slots (the
          raw value carries the readable content).
```

- [ ] **Step 3: Build and test**

Run: `dbtb int_focus__custom_field_log__unpivot` Expected: PASS —
`unique_combination_of_columns` on `(log_entry_id, slot_column_name)` passes.

- [ ] **Step 4: Spot-check the decode + grain**

```sql
select field_title, slot_title, slot_type,
  count(*) as n, countif(value_label is not null) as n_decoded
from `teamster-332318`.<your_dev_schema>.int_focus__custom_field_log__unpivot
group by 1, 2, 3
order by 1, 2
```

Expected: rows for both fields; `value_label` populated for the `select`-type
slots (`Vaccination`, `ARMS Student Field`) and null for `text` / `checkbox` /
`date` slots.

- [ ] **Step 5: Lint and commit**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/intermediate/int_focus__custom_field_log__unpivot.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__custom_field_log__unpivot.yml
git -C "$wt" add src/dbt/focus/models/intermediate/int_focus__custom_field_log__unpivot.sql src/dbt/focus/models/intermediate/properties/int_focus__custom_field_log__unpivot.yml
git -C "$wt" commit -m "feat(dbt): reshape Focus log custom fields in int_focus__custom_field_log__unpivot" -m "Refs #4258" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Build the full new graph together**

Run: `dbtb int_focus__custom_field_options+` Expected: all 9 new models build
and all tests pass in one run.

- [ ] **Confirm no staging drift**

Run: `git -C "$wt" status` — only files under `models/intermediate/`, `tests/`,
`docs/superpowers/`, and `src/dbt/focus/CLAUDE.md` changed. No `staging/`
changes.

- [ ] **Open the PR** using `.github/pull_request_template.md`, body referencing
      `Closes #4258`. Flag in the PR description that column-level PII tags
      follow the FERPA-broad stance pending People Operations confirmation.
