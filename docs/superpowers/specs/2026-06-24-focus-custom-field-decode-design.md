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

1. **The decode join needs the owner-type filter.** The documented join
   (`custom_field_select_options.source_id = custom_fields.id`) is correct but
   under-specified: `select_options.source_class` is a polymorphic owner type —
   the literal `CustomField` for entity fields, `CustomFieldLogColumn` for
   log-column slots — and the same numeric `source_id` occurs under both. Add
   `select_options.source_class = 'CustomField'` (or `'CustomFieldLogColumn'`
   for log slots) so the two owner types don't collide. Do **not** match the
   entity class (`SISSchool`, etc.) — `source_class` is never the entity class,
   so that filter returns zero rows (the trap that surfaced this).

2. **The entity stores the option `id`, not the `code`.** A `select` value is a
   single select-option **id** (e.g. `5538` → label `E - Elementary`), stored as
   an int. A `multiple` value is a **JSON-array string of option ids**
   (`["2795"]`). Decode joins the stored id to `select_options.id` and reads
   `label` (the `code` — `E`, `M` — is the Focus import/export value, never the
   stored value). `multiple` means parse-JSON + map each id, not split on a
   delimiter. Every current `multiple` value is single-element, but the format
   is a real JSON array, so decode handles N elements generically.

3. **A minority of fields back their option list with a dynamic `option_query`**
   (no rows in `custom_field_select_options`; Focus builds the list at render
   time from other tables). Among the in-scope projected fields, exactly **one**
   is `option_query`-backed: `FocusUser.profile_on_non_production_sites`
   (`custom_l790`). It is decodable — its query is
   `select id, title as label from user_profiles`, and `user_profiles` is staged
   — but skipped as low-value (12 of 181 users, one distinct code). All other
   in-scope fields resolve via stored options. See _Out of scope_ for the full
   `option_query` inventory.

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
- No decode of `option_query`-backed fields (inventoried under _Out of scope_;
  the one in-scope field is skipped as low-value).
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
| `int_focus__custom_field_log__unpivot` | Wide-to-long reshape of the two log-type fields       |

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
        select cast(id as string) as option_id, source_id, code, label
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomField'  -- keep inactive: decode historical values
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

- Grain / uniqueness: `option_id` (the select-option PK — globally unique,
  non-null, so no dedupe needed).
- The entity stores the option **id**, not its `code`; pivots join the stored
  value to `option_id`. `code` is the Focus import/export value and `label` the
  human name (the decode output).
- `inactive` options are kept — a stored value can reference an option later
  marked inactive.

### `int_focus__<entity>__pivot` (decode via UNPIVOT then join then PIVOT)

Pattern, shown for `int_focus__schools__pivot`:

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
        select id, column_name, option_id
        from encoded unpivot (
            option_id for column_name in (
                custom_100000004, custom_200000326, custom_50000002
            )
        )
    ),

    decoded as (
        select unpivoted.id, unpivoted.column_name, options.label
        from unpivoted
        left join {{ ref("int_focus__custom_field_options") }} as options
            on options.source_class = 'SISSchool'
            and options.column_name = unpivoted.column_name
            and options.option_id = unpivoted.option_id
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
    cross join unnest(json_value_array(users.education)) as element_id
    left join {{ ref("int_focus__custom_field_options") }} as options
        on element_id = options.option_id
        and options.source_class = 'FocusUser'
        and options.column_name = 'custom_2'
    group by users.staff_id
)
```

`profile_on_non_production_sites` (`custom_l790`) is `option_query`-backed and
is **omitted** from the pivot. It is decodable via a join to
`stg_focus__user_profiles` (`custom_l790 = user_profiles.id`, then `title`), but
skipped as low-value (12 of 181 users, one distinct code). Its code remains in
staging; a SQL comment documents the skip. See _Out of scope_ for the full
`option_query` inventory.

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

### `int_focus__custom_field_log__unpivot` (wide-to-long reshape)

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

- **Naming.** Decode-to-wide models use the `int_focus__<entity>__pivot`
  convention with `<slug>_label` columns; the wide-to-long log model uses the
  `__unpivot` suffix.
- **Tests.** Uniqueness test on every model (intermediate-layer requirement):
  entity PK on each `__pivot`, `option_id` on the crosswalk,
  `(log_entry_id, slot_column_name)` on the log model. Tests are warn-level
  unless a stronger signal is warranted; the crosswalk `option_id` is `error` (a
  duplicate there silently corrupts every decode).
- **PII.** Every pivot model and the log model is keyed by a student/staff
  identifier (a FERPA direct identifier), so each carries
  `config.meta.contains_pii: true` at the model level regardless of which
  columns are tagged. Decoded attributes — `sex`, `race_*`, `language`,
  residence/birth-linked values — are FERPA _indirect_ identifiers (PII under
  the "linked or linkable" standard, which applies here because they sit
  alongside the student key). FERPA-aligned tagging is therefore **broad** (tag
  these columns). The existing Focus staging precedent is narrower (omits
  gender/race/IDs); reconcile the two and confirm direct-only vs direct+indirect
  scope with People Operations before finalizing tags — this is a compliance
  call, not settled by this spec.
- **Descriptions.** Every new model and every column gets a `description:` in
  `properties/`. Describe decoded columns by their logic (decoded label for the
  named field). Data/column semantics go in descriptions, not CLAUDE.md.
- **Docs clarification.** Augment the "Focus field value codes" section of
  `src/dbt/focus/CLAUDE.md`: keep `select_options.source_id = custom_fields.id`,
  but add `select_options.source_class = 'CustomField'` (or
  `'CustomFieldLogColumn'` for log slots) to prevent `source_id` collisions
  across owner types, and note that `source_class` is never the entity class.

## Out of scope / follow-ups

- `option_query`-backed dynamic option lists (inventoried below).
- Any `rpt_` / mart / extract consuming these models.
- Other districts (only `kippmiami` ingests Focus).

### `option_query`-backed fields (not decoded)

These `select` fields generate their option list from a live Focus query against
other tables instead of `custom_field_select_options`, so they do not decode via
the crosswalk. Only `FocusUser.profile_on_non_production_sites` (`custom_l790`)
is projected in staging today, and it is skipped as low-value; the rest are not
projected. Recorded here so the set is captured if a future consumer needs one.

| source_class  | column_name                             | title                              | label source                                   |
| ------------- | --------------------------------------- | ---------------------------------- | ---------------------------------------------- |
| FocusUser     | `custom_l790`                           | Profile On Non-Production Sites    | `user_profiles` (projected; skipped)           |
| FocusUser     | `check_location`                        | Check Location                     | `gl_facilities`                                |
| FocusUser     | `charter_final_eval`                    | Final Evaluation Code              | `gl_pr_personnel_evaluation_codes`             |
| FocusUser     | `charter_eval_msp`                      | MSP                                | `gl_pr_measures_of_student_learning_growth`    |
| FocusUser     | `charter_mid_eval`                      | Midpoint Evaluation (new teachers) | `gl_pr_personnel_evaluation_codes`             |
| FocusUser     | `charter_prim_job`                      | Primary Job Code                   | `gl_pr_jobs_state`                             |
| FocusUser     | `charter_prim_schl`                     | Primary School                     | `gl_facilities`                                |
| FocusUser     | `custom_l1472`                          | Site Assignment (Primary)          | `schools`                                      |
| SISStudent    | `custom_fl_biliteracy_aappl`            | ACTFL AAPPL                        | options table (syear-scoped)                   |
| SISStudent    | `custom_fl_biliteracy_opi`              | ACTFL OPI                          | options table (syear-scoped)                   |
| SISStudent    | `custom_fl_biliteracy_asl`              | SLPI:ASL                           | options table (syear-scoped)                   |
| SISStudent    | `custom_fl_biliteracy_stamp4s`          | STAMP4S (Grade 7-Adult)            | options table (syear-scoped)                   |
| SISStudent    | `custom_fl_biliteracy_bcpo`             | Biliteracy Seal Portfolio Option   | options table (syear-scoped)                   |
| SISStudent    | `application_courses_selected_course_1` | Application Courses Selected 1     | `course_periods` + `courses` (syear-scoped)    |
| SISStudent    | `application_courses_selected_course_2` | Application Courses Selected 2     | `course_periods` + `courses` (syear-scoped)    |
| SISStudent    | `application_courses_selected_course_3` | Application Courses Selected 3     | `course_periods` + `courses` (syear-scoped)    |
| SISStudent    | `custom_992012001`                      | Bus Driver Name AM                 | `custom_field_log_entries`                     |
| SISStudent    | `custom_992012002`                      | Bus Driver Name PM                 | `custom_field_log_entries`                     |
| SISStudent    | `custom_l1216`                          | Future ESE Model Choice            | `custom_field_select_options` (source_id 1042) |
| CourseCatalog | `custom_field_15`                       | Industry Certification ID          | `florida_industry_certifications` (syear)      |
| CourseCatalog | `custom_field_16`                       | 2nd Industry Certification ID      | `florida_industry_certifications` (syear)      |
| CourseCatalog | `custom_field_18`                       | 3rd Industry Certification ID      | `florida_industry_certifications` (syear)      |

`SISSchool`, `StudentEnrollment`, `CoursePeriod`, and `Course` have none. The
catalog is the live source of truth — regenerate the current set with:

```sql
select cf.source_class, cf.column_name, cf.title, cf.option_query
from {{ ref("stg_focus__custom_fields") }} as cf
left join (
    select distinct source_id
    from {{ ref("stg_focus__custom_field_select_options") }}
    where source_class = 'CustomField'
) as o on cf.id = o.source_id
where cf.type in ('select', 'multiple')
    and cf.option_query is not null
    and o.source_id is null
```

## Open implementation checks

1. **Decode key is the option id.** Entities store `select_options.id`, not
   `code`; the crosswalk keys on `option_id` (the option PK), so it is naturally
   unique and needs no dedupe. Spot-check that each pivot decodes (non-null
   labels where the entity value is set) — a regression to code-keying shows up
   as all-null labels.
2. **`multiple` multi-element.** Current data is single-element; the `array_agg`
   decode handles N elements regardless. No additional work unless a
   multi-element value needs ordering guarantees beyond `order by label`.
3. **Log-slot select decode coverage.** Confirm the `select`-type log slots
   (`Vaccination`, `ARMS Student Field`) resolve via the
   `CustomFieldLogColumn`-keyed options before relying on `value_label`.
4. **Build order.** Crosswalk first, then the pivots and log model. Run
   `dbt deps` in the worktree before any build (fresh worktree has no
   `dbt_packages/`).
