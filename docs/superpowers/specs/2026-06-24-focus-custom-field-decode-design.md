# Focus SIS Wave 2 — decode encoded custom values + reshape log fields

Design spec for [#4258](https://github.com/TEAMSchools/teamster/issues/4258).
Deferred follow-up from Focus SIS Phase B (#4213).

## Context

The Phase B staging models project `select` / `multiple` custom-field values
inline but leave them as their stored Focus **option codes** (decode was out of
scope to keep staging contracts stable). This work decodes those codes to
human-readable labels, and reshapes the `log`-type custom fields into a usable
long shape.

All work is **additive intermediate models** under
`src/dbt/focus/models/intermediate/`. There are **no staging changes** — staging
stays encoded, and the H custom-field metadata staging is already merged. Models
build in `kippmiami` (the only district wired for Focus); district-internal, so
there is no prod-materialization gate.

## Findings from data profiling (Miami pull)

These reframe the issue and `focus/CLAUDE.md`, and are load-bearing for the
design:

1. **The documented decode join is wrong.**
   `custom_field_select_options.source_class` is the literal polymorphic value
   `CustomField` (for entity fields) or `CustomFieldLogColumn` (for log-column
   slots) — **not** the entity class (`SISSchool`, etc.). Joining on the entity
   class returns zero matches. The correct join is
   `select_options.source_id = custom_fields.id` alone, with
   `select_options.source_class = 'CustomField'`.

2. **`select` and `multiple` store differently.** `select` stores a **bare
   code** (`5539`, `E`). `multiple` stores a **JSON-array string** (`["2795"]`).
   Decode for `multiple` means parse-JSON + map each element, not split on a
   delimiter. In the current pull every `multiple` value is single-element, but
   the format is a real JSON array, so decode handles N elements generically.

3. **A minority of fields decode only via a dynamic `option_query`** (no rows in
   `custom_field_select_options`). Among the in-scope projected fields, exactly
   **one** is `option_query`-only: `FocusUser.profile_on_non_production_sites`
   (`custom_l790`). It is excluded from decode and documented; all other
   in-scope fields resolve via stored options.

4. **The `log` reshape is narrow.** All 24,224 `custom_field_log_entries` rows
   are `SISStudent`, across just **two** fields — `Immunization Compliance`
   (`field_id` 541) and `ARMS Student Field Tracker` (`field_id` 1119) — and
   1,514 students. Each entry has up to four typed slots (`LOG_FIELD1..4`) named
   by `custom_field_log_columns`. `created_at` / `updated_at` are fully
   populated; `completed_at` is always null; `syear` is populated only on ARMS.

## Goals

- Decode every in-scope projected `select` / `multiple` custom value to its
  label.
- Reshape the two populated `log`-type fields into a long, typed, decoded model.
- Provide a single reusable code-to-label crosswalk.
- Fix the wrong decode-join documentation in `focus/CLAUDE.md`.

## Non-goals (YAGNI)

- No `rpt_` / mart / extract layer — this pass builds the reusable intermediate
  foundation only. (Repo convention: an `rpt_` must sit between an intermediate
  model and any external consumer; one gets added when a concrete consumer
  appears.)
- No decode of `option_query`-only fields (would require running the live Focus
  query).
- No decode of non-`select`/`multiple` customs (`checkbox` Y/N, `text`,
  `numeric`, `date` are already human-readable).
- No staging changes.

## Architecture

Nine intermediate models:

| Model                                  | Role                                                  |
| -------------------------------------- | ----------------------------------------------------- |
| `int_focus__custom_field_options`      | Shared code-to-label crosswalk                        |
| `int_focus__students__pivot`           | Decoded labels for SISStudent select fields           |
| `int_focus__schools__pivot`            | Decoded labels for SISSchool select fields            |
| `int_focus__student_enrollment__pivot` | Decoded labels for StudentEnrollment select fields    |
| `int_focus__users__pivot`              | Decoded labels for FocusUser select + multiple fields |
| `int_focus__course_periods__pivot`     | Decoded labels for CoursePeriod select fields         |
| `int_focus__master_courses__pivot`     | Decoded labels for CourseCatalog select fields        |
| `int_focus__courses__pivot`            | Decoded labels for Course select fields               |
| `int_focus__custom_field_log`          | Long reshape of the two populated log-type fields     |

The existing `int_focus__student_enrollment` (title enrichment) is unchanged;
the new `int_focus__student_enrollment__pivot` is a separate decode-only model.

Each `__pivot` model is **labels-only**, keyed by the entity primary key. Codes
remain in staging untouched; a downstream consumer joins staging (codes) and the
pivot model (labels) on the PK.

### `int_focus__custom_field_options` (crosswalk)

```sql
with
    cf as (
        select id, source_class, lower(column_name) as column_name
        from {{ ref("stg_focus__custom_fields") }}
    ),

    opt as (
        select source_id, code, label
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomField'  -- keep inactive: decode historical values
    )

select
    cf.source_class,
    cf.column_name,
    opt.code,
    opt.label,
from opt
inner join cf on opt.source_id = cf.id
```

- Grain / uniqueness: `(source_class, column_name, code)`.
- `inactive` options are kept — a stored value can reference an option later
  marked inactive.
- If a field carries duplicate `code` rows (e.g. across `min_syear` /
  `max_syear`), dedupe with `dbt_utils.deduplicate` (`partition_by` the grain,
  `order_by updated_at desc`). Verify whether duplicates exist during
  implementation; only add the dedupe if the uniqueness test fails.

### `int_focus__<entity>__pivot` (decode via UNPIVOT then join then PIVOT)

Pattern, shown for `int_focus__schools__pivot`:

```sql
with
    encoded as (
        select
            school_id,
            cast(school_level as string) as custom_100000004,
            cast(school_type as string) as custom_200000326,
            cast(technical_center as string) as custom_50000002,
        from {{ ref("stg_focus__schools") }}
    ),

    unpivoted as (
        select school_id, column_name, code
        from encoded unpivot (
            code for column_name in (
                custom_100000004, custom_200000326, custom_50000002
            )
        )
    ),

    decoded as (
        select unpivoted.school_id, unpivoted.column_name, options.label
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on options.source_class = 'SISSchool'
            and options.column_name = unpivoted.column_name
            and options.code = unpivoted.code
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

Mechanics and rationale:

- The slug to catalog-`column_name` mapping lives once, in the `encoded` CTE
  aliases — `custom_100000004` greps straight back to staging's
  `custom_100000004 as school_level`. No magic field-id integers in the model.
- All encoded columns are cast to `string` in `encoded` so the mixed-type
  `select` columns share a type for `UNPIVOT` (codes compare as strings against
  the crosswalk).
- `UNPIVOT` excludes nulls by default, so an unset field yields no row and a
  null pivot column.
- `any_value(label)` is safe: each `(pk, column_name)` has exactly one row after
  the join. An unresolved code (none, given the inventory below) would yield a
  null label.
- Output label columns use the `<slug>_label` suffix.
- Uniqueness test on the entity PK (one row per entity).

#### `multiple` wrinkle — `int_focus__users__pivot`

A single `PIVOT` applies one aggregate to all fields, and `multiple` needs a
JSON-array explode plus `array_agg`. So `int_focus__users__pivot` PIVOTs its one
decodable `select` field (`active`), then left-joins an `education_label`
`array<string>` built with the CTE pattern (cross join `unnest` then join then
`array_agg`) — not a correlated subquery, per the BigQuery no-correlated-
subquery rule in `dbt/CLAUDE.md`:

```sql
education as (
    select
        users.staff_id,
        array_agg(options.label ignore nulls order by options.label)
            as education_label,
    from {{ ref("stg_focus__users") }} as users
    cross join unnest(json_value_array(users.education)) as code
    left join {{ ref("int_focus__custom_field_options") }} as options
        on options.source_class = 'FocusUser'
        and options.column_name = 'custom_2'
        and options.code = code
    group by users.staff_id
)
```

`profile_on_non_production_sites` (`custom_l790`) is `option_query`-only and is
**omitted** from the pivot (it cannot decode from the static table). Its code
remains available in staging; a SQL comment documents why it is excluded.

#### In-scope decode inventory

Authoritative map (catalog-confirmed; `field_id` shown for reference only — the
models join on `column_name`, not the id):

| Pivot model                            | source_class      | staging slug                                     | column_name        | field_id | type     | options |
| -------------------------------------- | ----------------- | ------------------------------------------------ | ------------------ | -------- | -------- | ------- |
| `int_focus__students__pivot`           | SISStudent        | `ethnicity_hispanic_or_latino`                   | `custom_100000105` | 73       | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `race_white`                                     | `custom_100000104` | 74       | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `race_black_or_african_american`                 | `custom_100000102` | 75       | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `race_asian`                                     | `custom_100000101` | 141      | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `sex`                                            | `custom_200000000` | 310      | select   | 3       |
| `int_focus__students__pivot`           | SISStudent        | `race_american_indian_or_alaska_native`          | `custom_100000100` | 368      | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `race_native_hawaiian_or_other_pacific_islander` | `custom_100000103` | 369      | select   | 2       |
| `int_focus__students__pivot`           | SISStudent        | `residence_county`                               | `custom_837`       | 374      | select   | 75      |
| `int_focus__students__pivot`           | SISStudent        | `language`                                       | `custom_200000005` | 434      | select   | 3       |
| `int_focus__schools__pivot`            | SISSchool         | `technical_center`                               | `custom_50000002`  | 678      | select   | 3       |
| `int_focus__schools__pivot`            | SISSchool         | `school_level`                                   | `custom_100000004` | 681      | select   | 5       |
| `int_focus__schools__pivot`            | SISSchool         | `school_type`                                    | `custom_200000326` | 682      | select   | 12      |
| `int_focus__student_enrollment__pivot` | StudentEnrollment | `prior_district`                                 | `custom_1`         | 1486     | select   | 82      |
| `int_focus__student_enrollment__pivot` | StudentEnrollment | `prior_state`                                    | `custom_2`         | 1487     | select   | 72      |
| `int_focus__student_enrollment__pivot` | StudentEnrollment | `prior_country`                                  | `custom_3`         | 1488     | select   | 288     |
| `int_focus__student_enrollment__pivot` | StudentEnrollment | `educational_choice`                             | `custom_4`         | 1489     | select   | 8       |
| `int_focus__student_enrollment__pivot` | StudentEnrollment | `student_offender_transfer`                      | `custom_6`         | 1491     | select   | 2       |
| `int_focus__users__pivot`              | FocusUser         | `active`                                         | `custom_319000004` | 513      | select   | 2       |
| `int_focus__users__pivot`              | FocusUser         | `education`                                      | `custom_2`         | 508      | multiple | 5       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `fefp_number`                                    | `custom_2`         | 1508     | select   | 11      |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `scheduling_method`                              | `custom_4`         | 1513     | select   | 9       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `facility_type`                                  | `custom_6`         | 1516     | select   | 21      |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `cert_licensure_qual_status`                     | `custom_28`        | 1530     | select   | 13      |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `highly_qualified`                               | `custom_5`         | 1531     | select   | 9       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `reading_intervention_component`                 | `custom_25`        | 1534     | select   | 4       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `location_of_student`                            | `custom_33`        | 1554     | select   | 4       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `eoc_exam_term`                                  | `custom_34`        | 1560     | select   | 4       |
| `int_focus__course_periods__pivot`     | CoursePeriod      | `basic_skills_exam`                              | `custom_22`        | 1544     | select   | 14      |
| `int_focus__master_courses__pivot`     | CourseCatalog     | `fefp`                                           | `custom_field_5`   | 1738     | select   | 11      |
| `int_focus__master_courses__pivot`     | CourseCatalog     | `course_flag_1`                                  | `custom_field_6`   | 1739     | select   | 18      |
| `int_focus__master_courses__pivot`     | CourseCatalog     | `dual_enrollment_indicator`                      | `custom_field_13`  | 1731     | select   | 5       |
| `int_focus__courses__pivot`            | Course            | `course_sequence`                                | `custom_4`         | 1724     | select   | 12      |
| `int_focus__courses__pivot`            | Course            | `ocp`                                            | `custom_3`         | 1723     | select   | 78      |

Excluded (in-scope entity, but not decodable): `FocusUser`
`profile_on_non_production_sites` (`custom_l790`, field 790) —
`option_query`-only.

### `int_focus__custom_field_log` (long reshape)

`UNPIVOT` `log_field1..log_field30` (nulls dropped), inner-join
`stg_focus__custom_field_log_columns` on `(field_id, LOG_FIELDn)` to label and
type each slot, then decode `select`-type slots via
`stg_focus__custom_field_select_options` keyed on
`source_class = 'CustomFieldLogColumn'`,
`source_id = custom_field_log_columns.id`.

- Columns: `log_entry_id`, `student_id` (`source_id`), `school_id`, `field_id`,
  `field_title`, `slot_sort_order`, `slot_column_name`, `slot_title`,
  `slot_type`, `value`, `value_label`, `syear`, `created_at`, `updated_at`.
- Grain / uniqueness: `(log_entry_id, slot_column_name)`.
- `completed_at` is omitted (always null). `created_at` / `updated_at` are the
  recorded-at timestamps.
- Unpivot all 30 slots for forward-safety; the inner join to
  `custom_field_log_columns` drops slots a field does not define (current data
  uses slots 1–4 only).
- `value_label` is the decoded label for `select` slots; for non-`select` slots
  it is null (the raw `value` carries the readable content).

## Cross-cutting

- **Naming.** Decode models use the `int_focus__<entity>__pivot` convention.
  Label columns use the `<slug>_label` suffix.
- **Tests.** Uniqueness test on every model (intermediate-layer requirement):
  entity PK on each `__pivot`, `(source_class, column_name, code)` on the
  crosswalk, `(log_entry_id, slot_column_name)` on the log model. Tests are
  warn-level unless a stronger signal is warranted; the crosswalk grain is
  `error` (a duplicate there silently corrupts every decode).
- **PII.** Student- and staff-level pivot models and the log model carry PII via
  their entity keys and some decoded values (e.g. `sex`, `race_*`, `language`,
  residence/birth-linked attributes). Tag `config.meta.contains_pii: true`
  consistent with the existing Focus staging precedent; confirm direct-only vs
  direct+indirect scope with the field owner before finalizing tags.
- **Descriptions.** Every new model and every column gets a `description:` in
  `properties/`. Describe decoded columns by their logic (decoded label for the
  named field). Data/column semantics go in descriptions, not CLAUDE.md.
- **Docs fix.** Correct the "Focus field value codes" section of
  `src/dbt/focus/CLAUDE.md`: the join is
  `select_options.source_id = custom_fields.id` with
  `select_options.source_class = 'CustomField'` (or `'CustomFieldLogColumn'` for
  log slots), **not** a match on the entity `source_class`.

## Out of scope / follow-ups

- `option_query`-backed dynamic option lists (one in-scope field today).
- Any `rpt_` / mart / extract consuming these models.
- Other districts (only `kippmiami` ingests Focus).

## Open implementation checks

1. **Crosswalk duplicates.** Build the crosswalk, run its uniqueness test; add
   `dbt_utils.deduplicate` only if `(source_class, column_name, code)` is not
   already unique.
2. **`multiple` multi-element.** Current data is single-element; the `array_agg`
   decode handles N elements regardless. No additional work unless a
   multi-element value needs ordering guarantees beyond `order by label`.
3. **Log-slot select decode coverage.** Confirm the `select`-type log slots
   (`Vaccination`, `ARMS Student Field`) resolve via the
   `CustomFieldLogColumn`-keyed options before relying on `value_label`.
4. **Build order.** Crosswalk first, then the pivots and log model. Run
   `dbt deps` in the worktree before any build (fresh worktree has no
   `dbt_packages/`).
