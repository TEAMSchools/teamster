# Assessments grain split — design

Tracking issue: [#3800](https://github.com/TEAMSchools/teamster/issues/3800).

## Problem

`int_assessments__assessments` is member-grain (one row per Illuminate
`assessment_id`) but carries `canonical_*` columns as denormalized
pass-throughs. The model conflates two grains: member and canonical.

Consequence: downstream consumers split awkwardly.

- `dim_assessment_administrations.illuminate_administrations` wants
  canonical-grain. To collapse the over-fan from member-grain input, it uses
  `SELECT DISTINCT` over `(canonical_*, region)` tuples — flagged by
  `src/dbt/CLAUDE.md` "no manual deduplication" and tracked under #3800 via PR
  #3798's TODO comment.
- `dim_assessments.illuminate_assessments`,
  `bridge_assessment_administration_members`, `int_assessments__scaffold`,
  `int_assessments__performance_bands`, `fct_assessment_scores_*`, expectation
  bridges, and `rpt_appsheet__assessments` want member-grain. They ignore the
  `canonical_*` columns or read them as label pass-throughs.

The right shape is two intermediate models, one per grain, with an explicit FK
between them.

## End state

Two intermediate models with explicit FK linkage:

```text
int_assessments__assessments_members  (PK: assessment_id)
    | FK: canonical_assessment_id
    v
int_assessments__assessments_canonical  (PK: canonical_assessment_id)
```

### `int_assessments__assessments_members` (member-grain)

One row per Illuminate `assessment_id`. Replaces today's
`int_assessments__assessments` after PR 2's rename.

Columns:

- `assessment_id` (PK, INT64)
- `canonical_assessment_id` (FK to `int_assessments__assessments_canonical`,
  INT64) — computed via the existing
  `first_value(assessment_id) over canonical_w` window
- `title`
- `academic_year`
- `academic_year_clean`
- `scope`
- `subject_area`
- `module_code`
- `module_type`
- `module_sequence`
- `grade_level_id`
- `illuminate_grade_level_id`
- `administered_at` (raw member timestamp)
- `regions_assessed`
- `regions_assessed_array`
- `regions_report_card`
- `regions_progress_report`
- `creator_first_name`
- `creator_last_name`
- `performance_band_set_id`
- `assessment_type`
- `tags`
- `is_internal_assessment`

Columns dropped from today's model (move to canonical):

- `canonical_title`
- `canonical_administered_at`
- `canonical_grade_level_id`
- `administered_date` (derived from `canonical_administered_at`)
- `grade_level` (derived from `canonical_grade_level_id - 1`)

### `int_assessments__assessments_canonical` (canonical-grain)

One row per `canonical_assessment_id`. New model.

Columns:

- `canonical_assessment_id` (PK, INT64)
- `title` — canonical pick
- `administered_at` — canonical pick
- `administered_date` — `cast(administered_at as date)`
- `grade_level_id` — canonical pick
- `grade_level` — `grade_level_id - 1`
- `subject_area` — constant within partition; pick or `any_value`
- `scope` — constant within partition
- `module_code` — constant within partition
- `academic_year` — constant within partition
- `academic_year_clean` — constant within partition
- `regions_array` — union of member regions via `array_agg(distinct region)`
  after `unnest(regions_assessed_array)`
- `is_internal_assessment` — always TRUE in this model (filter applied upstream)

`module_type`, `module_sequence`, `performance_band_set_id`, `tags`, `creator_*`
— not included in canonical. They're member-level signals; if a consumer needs
them, it reads members.

Built as:

```sql
with
    canonical_picks as (
        {{ dbt_utils.deduplicate(
            relation=ref('int_assessments__assessments_members'),
            partition_by='canonical_assessment_id',
            order_by='assessment_id'
        ) }}
    ),
    canonical_regions as (
        select
            canonical_assessment_id,
            array_agg(distinct region) as regions_array,
        from {{ ref('int_assessments__assessments_members') }},
        unnest(regions_assessed_array) as region
        where is_internal_assessment
        group by canonical_assessment_id
    )
select
    p.canonical_assessment_id,
    p.title,
    p.administered_at,
    cast(p.administered_at as date) as administered_date,
    p.subject_area,
    p.scope,
    p.module_code,
    p.academic_year,
    p.academic_year_clean,
    p.grade_level_id,
    p.grade_level_id - 1 as grade_level,
    p.is_internal_assessment,
    r.regions_array,
from canonical_picks as p
inner join canonical_regions as r
    on p.canonical_assessment_id = r.canonical_assessment_id
where p.is_internal_assessment
```

`dbt_utils.deduplicate(partition_by=canonical_assessment_id, order_by=assessment_id)`
produces the same deterministic pick as today's
`first_value(... order by assessment_id) over canonical_w` window — both select
the member with the lowest `assessment_id` in the canonical group. Satisfies
`src/dbt/CLAUDE.md` "Canonical attributes from a partition" (all attrs from one
row, not independent `min()` calls).

### Mart-layer reads

After PR 3:

| Mart / model                                                  | Reads                                                                    | Grain     |
| ------------------------------------------------------------- | ------------------------------------------------------------------------ | --------- |
| `dim_assessment_administrations.illuminate_administrations`   | `assessments_canonical`                                                  | canonical |
| `dim_assessments.illuminate_assessments`                      | `assessments_members`                                                    | member    |
| `bridge_assessment_administration_members`                    | `assessments_members`                                                    | member    |
| `int_assessments__scaffold`                                   | `assessments_members` + join `assessments_canonical` for canonical attrs | member    |
| `int_assessments__performance_bands`                          | `assessments_members`                                                    | member    |
| `fct_assessment_scores_*`                                     | `assessments_members`                                                    | member    |
| `bridge_assessment_expectations_*`                            | `assessments_members`                                                    | member    |
| `rpt_appsheet__assessments`                                   | `assessments_members`                                                    | member    |
| `rpt_tableau__ddi_audit`, `rpt_tableau__assessment_tag_audit` | `assessments_members`                                                    | member    |

## PR sequence

### PR 1 — Foundation (this branch)

Scope:

- Add `int_assessments__assessments_canonical.sql` and its properties YAML.
- Update `dim_assessment_administrations.sql`:
  - Drop the inline `canonical_regions` CTE (logic moves into the new model).
  - Rewrite `illuminate_administrations` as a plain SELECT from
    `assessments_canonical`, with `cross join unnest(regions_array)`. No
    DISTINCT.
  - Remove the `TODO(#3800)` comment.
- `int_assessments__assessments` untouched.

Hash impact:

- Dim's surrogate key inputs are unchanged:
  `(assessment_type, module_code, administered_date, academic_year, _dbt_source_project, administration_period, source_assessment_id, test_type)`.
  `source_assessment_id` comes from `canonical_assessment_id` in both old and
  new code; same for the other inputs. Hash-stable.
- Bridge untouched in PR 1.

Tests:

- `assessments_canonical` PK uniqueness on `canonical_assessment_id`.
- Existing `dim_assessment_administrations` tests pass unchanged.

Verification (per `superpowers:finishing-a-development-branch` override in
project CLAUDE.md):
`uv run dbt build --select int_assessments__assessments_canonical+` against
`kipptaf`, plus dim/bridge row-count diff vs prod to confirm hash-stable.

### PR 2 — Rename

Scope:

- Rename `int_assessments__assessments.sql` →
  `int_assessments__assessments_members.sql`.
- Rename the properties YAML accordingly.
- Update every `ref('int_assessments__assessments')` →
  `ref('int_assessments__assessments_members')` across the codebase.
- Update `int_assessments__assessments_canonical`'s `ref()` to the new name.
- Update YAML cross-references (`config.meta.source_column` pointers,
  description prose mentioning the old name).

Hash impact: none. Pure rename.

Tests: full kipptaf build to confirm no broken refs.

### PR 3 — Pass-through drop + consumer migration

Scope:

- Drop from `assessments_members`: `canonical_title`,
  `canonical_administered_at`, `canonical_grade_level_id`, `administered_date`,
  `grade_level`.
- Per-consumer migration:
  - `int_assessments__scaffold` — joins `assessments_canonical` on
    `canonical_assessment_id` to pull `canonical_title`,
    `canonical_administered_at`, `canonical_grade_level_id` (which become plain
    `title`, `administered_at`, `grade_level_id` on the canonical side). Output
    column names preserved where downstream relies on them.
  - `int_assessments__performance_bands` — audit; likely no canonical attrs
    needed.
  - `fct_assessment_scores_*` — audit; comments say "raw academic_year", which
    is member-grain. Likely no canonical attrs needed.
  - `bridge_assessment_expectations_*` — audit; comments say "recover raw
    values", which is member-grain. Likely no canonical attrs needed.
  - `rpt_appsheet__assessments` — uses
    `select * except (regions_assessed_array)`. Either restate as an explicit
    column list (preferred) or join canonical to retain the previously-exposed
    `canonical_*` columns. Decision deferred to PR 3 work pending AppSheet
    exposure check.
  - `dim_assessments.illuminate_assessments` — uses `title`, `subject_area`,
    `scope`, `module_code`, `module_type`, `grade_level`,
    `is_internal_assessment`. `grade_level` is member-grain-derived (today it's
    `canonical_grade_level_id - 1` projected). Verify whether `dim_assessments`
    wants member-level or canonical-level `grade_level` — PR 3 audit will
    surface.
  - `rpt_tableau__ddi_audit`, `rpt_tableau__assessment_tag_audit` — audit.

Hash impact: per-consumer audit. Mart surrogate-key inputs that reference
removed columns get rehashed; this is the spec-acknowledged blast point.

Tests: per-consumer test runs + full kipptaf build + manual hash-diff against
prod for affected marts.

Closes #3800.

## Open items / known unknowns

- **PR 3 per-consumer migration plan**. Spec defines the end state; the
  per-consumer migration list and any hash-change consequences emerge during PR
  3 work. We can pre-audit during PR 1 or PR 2 if useful, but it's not a blocker
  for PR 1.
- **`grade_level` semantics in `dim_assessments`**. Today,
  `int_assessments__assessments.grade_level` is `canonical_grade_level_id - 1` —
  canonical-grain semantics on a member-grain row. PR 3 must decide:
  member-level (each member's own grade_level) or canonical-level (the canonical
  group's grade_level).
- **`assessments_canonical` is_internal_assessment column**. Always TRUE given
  the upstream filter; included for symmetry but redundant. Drop-decision
  deferred to PR 1 review.
- **`creator_*`, `tags`, `module_type`, `module_sequence`,
  `performance_band_set_id`** placement — included on members, not canonical. PR
  3 audit confirms no current consumer wants them at canonical grain.

## Out of scope

- Restructuring state assessments (PARCC, NJSLA, FAST, FSA, etc.) or college
  assessments. Those go through their own intermediate models and don't have the
  member/canonical split.
- Changes to `int_illuminate__assessments` (upstream of members) or
  `stg_google_appsheet__illuminate_assessments_extension`.
- Anything in `dim_assessment_administrations` outside the
  `illuminate_administrations` CTE.
