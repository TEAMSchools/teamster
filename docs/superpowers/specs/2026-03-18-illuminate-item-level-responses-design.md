# Design: Illuminate Item-Level Student Response Data

**Date**: 2026-03-18 **Status**: Approved

## Background

Illuminate stores item-level student response data in
`dna_assessments.students_assessments_responses` — one row per student ×
question × assessment attempt. This table has never been ingested. Currently the
platform only reports overall, standard, and group scores. There is demand to
analyze how each student answered each question on multiple choice tests, and
whether their response was correct.

## Scope

Option A (staging + intermediate only). A reporting extract is deferred — the
shape of the consumer-facing output is not yet determined. The intermediate
model is an internal building block and should not be consumed directly by
external tools or reports; a reporting view will be built on top of it when the
presentation format is decided. That reporting view acts as a buffer between
external dependencies and internal schema evolution.

## New Source Tables

Four new tables added to the DLT ingestion pipeline from the Illuminate
PostgreSQL database (`dna_assessments` schema):

| Table                            | Description                                                                          | Size   | Notes                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------- |
| `students_assessments_responses` | Core item-level grain: one row per student × question × attempt                      | Large  | Needs `dagster/priority: "1"` and CPU resource tags — see rationale below |
| `responses`                      | Lookup: response text (e.g. "A", "B", "C", "D")                                      | Small  |                                                                           |
| `field_responses`                | Maps `(field_id, response_id, version_id)` → `points` (correctness) + `choice` label | Medium | Composite index on `(field_id, response_id, version_id)` in Postgres      |
| `fields`                         | Assessment item metadata: ordering, question body, type, soft-delete                 | Medium | See array type note below                                                 |

All four are added to `illuminate.yaml` under `dna_assessments`, registered in
`sources-illuminate.yml` under `illuminate_dna_assessments`, and get thin
`select * from source` staging models under `models/illuminate/dlt/staging/`.

`sources-illuminate.yml` source registration: the new entry uses `name: fields`
under `illuminate_dna_assessments`. No `identifier:` aliasing is needed — the
`dna_assessments` and `dna_repositories` sources land in separate BigQuery
datasets (`dagster_kipptaf_dlt_illuminate_dna_assessments` vs.
`dagster_kipptaf_dlt_illuminate_dna_repositories`), so no dbt-level name
collision occurs with the existing
`name: repository_fields / identifier: fields` entry under
`illuminate_dna_repositories`.

### Array type note

`dna_assessments.fields` contains two Postgres array-typed columns:

- `sort_order` (`_int4` — integer array)
- `sheet_responses` (`_varchar` — varchar array)

DLT with the PyArrow backend will ingest these as BigQuery REPEATED fields. The
staging model passes them through unchanged. These columns are not used in the
intermediate model but may matter for future consumers — treat with care if
referenced downstream.

## Dagster Assets

### `students_assessments_responses`

`build_illuminate_dlt_assets()` accepts an optional `filter_date_taken` boolean
(default `False`) that adds a `WHERE date_taken <= '9999-12-31'` callback to
handle PostgreSQL `infinity` date values that break psycopg. The existing
`agg_student_responses` and `students_assessments` entries set this to `true`
because they contain a `date_taken` column. `students_assessments_responses` has
no `date_taken` column (its columns are `student_assessment_response_id`,
`assessment_id`, `student_assessment_id`, `field_id`, `response_id`,
`version_id`, `manual_score` only), so `filter_date_taken` does not apply and
should not be set.

`students_assessments_responses` is expected to be significantly larger than
`agg_student_responses` because it is a finer grain (one row per question within
each student assessment attempt, versus one summary row per attempt). It
receives both `dagster/priority: "1"` and CPU resource tags, matching the
heavier `agg_student_responses_group` config rather than the lighter
`agg_student_responses` config:

```yaml
- table_name: students_assessments_responses
  op_tags:
    dagster/priority: "1"
    dagster-k8s/config:
      container_config:
        resources:
          requests:
            cpu: 500m
          limits:
            cpu: 1000m
```

### Other new tables

`responses`, `field_responses`, and `fields` get no special resource tags
(small/medium tables, no `date_taken` columns).

## Schedules

`students_assessments_responses` is added to
`illuminate_dlt_hourly_asset_job_schedule` alongside the other high-frequency
`dna_assessments` assets (`agg_student_responses`,
`agg_student_responses_group`, `agg_student_responses_standard`,
`students_assessments`). Assessment response data changes throughout the day as
teachers grade and students complete assessments.

`responses`, `field_responses`, and `fields` are reference/lookup tables that
change infrequently. They are added to `illuminate_dlt_daily_asset_job_schedule`
alongside other reference tables (`performance_bands`, `reporting_groups`,
`dna_repositories/fields`, etc.).

## Staging Models

Four new models under `models/illuminate/dlt/staging/`, each with a
corresponding properties YAML under `models/illuminate/dlt/staging/properties/`.
`materialized: table` and `contract: enforced: true` are inherited from
`dbt_project.yml` directory defaults — do not repeat them per-model.

| Model                                                             | Source table                     | Uniqueness test                                                                    |
| ----------------------------------------------------------------- | -------------------------------- | ---------------------------------------------------------------------------------- |
| `stg_illuminate__dna_assessments__students_assessments_responses` | `students_assessments_responses` | `unique` on `student_assessment_response_id`                                       |
| `stg_illuminate__dna_assessments__responses`                      | `responses`                      | `unique` on `response_id`                                                          |
| `stg_illuminate__dna_assessments__field_responses`                | `field_responses`                | `dbt_utils.unique_combination_of_columns` on `(field_id, response_id, version_id)` |
| `stg_illuminate__dna_assessments__fields`                         | `fields`                         | `unique` on `field_id`                                                             |

All uniqueness tests use `config: store_failures: true`.

Naming follows the existing convention: `stg_illuminate__<schema>__<table>`.

Note: `stg_illuminate__dna_assessments__fields` is distinct from the existing
`stg_illuminate__dna_repositories__repository_fields`, which covers a different
table in a different schema with different columns (repository-level fields, not
assessment item fields).

## Intermediate Model

**`int_illuminate__student_item_responses`**

Properties YAML at
`models/illuminate/dlt/intermediate/properties/int_illuminate__student_item_responses.yml`.

**Materialization**: view (global default — `dlt/intermediate/` has no
directory-level materialization setting in `dbt_project.yml`, and the existing
comparable models such as `int_illuminate__agg_student_responses` are all
views). No override required; follow the existing pattern.

**Grain**: one row per `student_assessment_response_id` (student × question ×
assessment attempt).

**Uniqueness test**: `unique` on `student_assessment_response_id` with
`config: store_failures: true`.

### Joins

All joins are INNER. All FK columns in `students_assessments_responses`
(`field_id`, `response_id`, `version_id`) are NOT NULL per the Illuminate
schema, so INNER joins are safe and correct — no rows are dropped due to nulls.

```
students_assessments_responses (sar)
  INNER JOIN responses (r)         on sar.response_id = r.response_id
  INNER JOIN field_responses (fr)  on sar.field_id = fr.field_id
                                   AND sar.response_id = fr.response_id
                                   AND sar.version_id = fr.version_id
  INNER JOIN fields (f)            on sar.field_id = f.field_id
                                   AND f.deleted_at IS NULL
```

`f.deleted_at IS NULL` belongs in the `ON` clause per project SQL conventions:
row-filter conditions on the **preserved** table belong in `WHERE`; conditions
on a joined (non-preserved) table belong in `ON`.

### Output Columns

| Column                           | Source             | Type    | Notes                                                                                             |
| -------------------------------- | ------------------ | ------- | ------------------------------------------------------------------------------------------------- |
| `student_assessment_response_id` | `sar`              | int64   | Uniqueness key                                                                                    |
| `student_assessment_id`          | `sar`              | int64   | Join handle for student/score context via `stg_illuminate__dna_assessments__students_assessments` |
| `assessment_id`                  | `sar`              | int64   |                                                                                                   |
| `version_id`                     | `sar`              | int64   |                                                                                                   |
| `field_id`                       | `sar`              | int64   |                                                                                                   |
| `field_order`                    | `f.order`          | int64   | Aliased from SQL reserved word `order`; question position within assessment                       |
| `response_id`                    | `sar`              | int64   |                                                                                                   |
| `response`                       | `r.response`       | string  | Answer text e.g. "A", "B", "C", "D"                                                               |
| `is_correct`                     | `fr.points > 0`    | boolean | True when student selected the correct answer                                                     |
| `points`                         | `fr.points`        | numeric | Raw points awarded for this response                                                              |
| `manual_score`                   | `sar.manual_score` | boolean | Whether score was entered manually                                                                |

### What is NOT in this model

- Student responses for soft-deleted assessment items — excluded intentionally
  by the `f.deleted_at IS NULL` ON clause condition
- Student demographics (name, grade level, local ID) — join to
  `stg_illuminate__dna_assessments__students_assessments` →
  `stg_illuminate__public__students` downstream
- Overall/standard/group scores — already in
  `int_illuminate__agg_student_responses`
- Question body text (`fields.body`) — available via join to
  `stg_illuminate__dna_assessments__fields` if needed downstream
- `field_responses.choice` — not yet confirmed whether this is equivalent to
  `responses.response` or carries distinct information (e.g. a display label vs.
  full response text). Must be validated against actual ingested data during
  implementation before deciding whether to include it

## Out of Scope

- Pivoting (wide format by question number) — too rigid for variable question
  counts; left to consuming tools
- `students_assessments_text_responses` (open-response/free-text answers) —
  separate table, different use case, not included
- Reporting extract model (`rpt_gsheets__*`, `rpt_tableau__*`) — deferred
  pending determination of presentation format; will be built on top of the
  intermediate when ready
