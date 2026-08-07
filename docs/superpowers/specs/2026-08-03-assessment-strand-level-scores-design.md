# Strand-level assessment scores: DIBELS subtests and i-Ready domains

Issue: [#4708](https://github.com/TEAMSchools/teamster/issues/4708)

Depends on: [#4706](https://github.com/TEAMSchools/teamster/issues/4706) /
[#4709](https://github.com/TEAMSchools/teamster/pull/4709)
(`int_iready__domain_unpivot` placement/`scale_score`) — **merged**. See
_i-Ready_ below for what landed and the one column still outstanding.

## Problem

`fct_assessment_scores_enrollment_scoped` carries only the summary score for the
two vendor benchmark diagnostics:

- **DIBELS** — the `dibels_scores` CTE filters `measure_standard = 'Composite'`,
  so subtest results (Nonsense Word Fluency, Phoneme Segmentation Fluency, Oral
  Reading Fluency, Letter Naming Fluency, etc.) never reach the mart or Cube.
- **i-Ready** — the `iready_scores_raw` CTE reads only the subject-level
  diagnostic row from `int_iready__diagnostic_results`, so the 14 per-domain
  results (Phonics, Vocabulary, Comprehension, Algebra and Algebraic Thinking,
  etc.) are absent.

Analysts want strand and domain level cuts for both sources. Internal Illuminate
assessments already model this exact shape through the `response_type` column
family, so the vendor breakdowns should reuse that pattern rather than introduce
a parallel one.

## Rejected approach: widen `module_code`

The obvious change — drop the `Composite` filter and let `measure_standard` flow
into `module_code` — produces FK orphans. `dim_assessments` and
`dim_assessment_administrations` are **siblings**, not descendants, of this
fact: each independently re-derives its DIBELS rows from
`int_amplify__all_assessments` with the same
`assessment_type = 'Benchmark' and measure_standard = 'Composite'` filter. Every
subtest row would hash an `assessment_administration_key` and `assessment_key`
that exist in neither dim.

The failure would be quiet rather than loud. Cube's `count_scores`,
`_sum_proficient`, and both `pct_proficient_*` measures filter
`{student_assessments.assessment_key} IS NOT NULL`, so orphaned rows would be
silently excluded from those measures while still inflating the ungated
`avg_scale_score` and the row-level dimensions — and `module_code` is not
exposed on the scores cube, so no consumer could scope around it.

## Design

### Discriminator columns

Breakdown rows populate the existing `response_type` family. Values follow what
is already in the fact, verified against prod:

| `response_type` | `_code` | `_description` | `_root_description` | shape                       |
| --------------- | ------- | -------------- | ------------------- | --------------------------- |
| `overall`       | NULL    | NULL           | NULL                | Illuminate summary score    |
| `group`         | NULL    | populated      | NULL                | named category breakdown    |
| `standard`      | coded   | full text      | populated           | CCSS-style standard         |
| NULL            | NULL    | NULL           | NULL                | every non-Illuminate source |

`'group'` is the correct target: a named category-level breakdown carrying no
standards code and no parent-domain rollup. A DIBELS subtest name and an i-Ready
domain name both fit that shape exactly. `'standard'` does not — neither source
has a CCSS-style code or a parent hierarchy.

So, for both sources:

```text
summary row    response_type = NULL,    response_type_description = NULL
breakdown row  response_type = 'group', response_type_description = <name>
```

`response_type_code` and `response_type_root_description` stay NULL throughout,
matching the `'group'` precedent.

**Summary rows keep `response_type = NULL` rather than becoming `'overall'`.**
This keeps the change purely additive. `assessment-cube-reference.md` documents
`response_type notSet` as the filter for a vendor summary row; promoting those
rows to `'overall'` would make every query following that documented pattern
return zero rows silently. Unifying `response_type` across all sources is a
worthwhile separate cleanup — it would have to cover state assessments too.

### DIBELS

Rewrite the `dibels_scores` CTE in
`fct_assessment_scores_enrollment_scoped.sql`:

```sql
-- module_code stays the literal 'Composite' so every DIBELS row -- summary and
-- subtest alike -- resolves the same assessment_administration_key and
-- assessment_key. dim_assessments and dim_assessment_administrations are
-- Composite-grain siblings of this fact and carry no subtest rows.
dibels_scores as (
    select
        student_number,
        academic_year,
        illuminate_subject,
        `period` as administration_period,
        client_date as test_date,
        _dbt_source_project,

        measure_standard_level as proficiency_level,

        'dibels' as score_source,
        'Composite' as module_code,

        cast(measure_standard_score as numeric) as scale_score,
        cast(measure_percentile as numeric) as national_percentile,

        measure_standard_level_int >= 3 as is_mastery,

        case when measure_standard != 'Composite' then 'group' end as response_type,

        case
            when measure_standard != 'Composite' then measure_standard
        end as response_type_description,
    from {{ ref("int_amplify__all_assessments") }}
    where assessment_type = 'Benchmark' and client_date is not null
),
```

Only `and measure_standard = 'Composite'` leaves the `where` clause. The
`assessment_type = 'Benchmark'` filter stays, so progress-monitoring rows remain
out of scope.

`is_mastery` needs no special handling: `measure_standard_level_int` is a
pass-through column populated on every `measure_standard` row in
`int_amplify__all_assessments`, not a Composite-only derivation, so the existing
`>= 3` threshold applies per subtest unchanged.

### i-Ready

#### What #4709 landed

`int_iready__domain_unpivot` now exposes `domain_name` (clean slug),
`placement`, `relative_placement`, `scale_score`, `test_round`, and
`_dbt_source_project`. Two things changed versus what this spec originally
assumed:

- **`illuminate_subject` was NOT included.** It is required: the vendor branch
  joins the resolver on `va.illuminate_subject = sr.subject_area`, so domain
  rows without it match nothing and the INNER JOIN drops all of them. Close this
  by adding the pass-through to `int_iready__domain_unpivot` as the first commit
  of this work — a one-line additive edit to the CTE and final `SELECT` plus a
  `properties.yml` entry, exactly matching how `test_round` and
  `_dbt_source_project` were just added. The marts convention explicitly permits
  additive upstream edits in a mart-focused PR, so this needs no separate
  cross-team dependency. Do NOT re-derive the `subject`-to-`illuminate_subject`
  mapping in the fact: `int_iready__diagnostic_results` already derives it, and
  duplicating a two-value translation downstream is the pattern this repo
  avoids.
- **The model now applies `where relative_placement is not null` itself**, and
  its description documents that inclusion rule. This is deliberate: with a
  three-column tuple `UNPIVOT`, BigQuery's implicit null-drop only removes a
  domain when all three values are null, so a tuple carrying a `placement` or
  `scale_score` but no `relative_placement` would otherwise survive. The fact
  therefore does NOT repeat that predicate — see the filter note in the CTE
  below.

The existing `iready_scores_raw` CTE stays as the subject-level anchor, gaining
only the two NULL discriminator literals for the union. A new sibling CTE adds
domain rows:

```sql
-- Domain-level rows. module_code stays the subject, for the same
-- FK-resolution reason as DIBELS above.
--
-- 'Not Assessed' is i-Ready's explicit not-administered marker (present only in
-- phonological awareness and high frequency words) and is excluded. A domain
-- with a placement but no scale score IS retained: the grade-level placement is
-- the primary domain signal, and the fact already carries scoreless rows
-- (internal Illuminate rows have a null scale_score throughout).
--
-- No 'relative_placement is not null' predicate here: int_iready__domain_unpivot
-- enforces it upstream as its documented inclusion rule (#4709). Repeating it
-- would imply the guarantee lives here.
iready_domain_scores_raw as (
    select
        student_id as student_number,
        academic_year_int as academic_year,
        `subject` as module_code,
        illuminate_subject,
        test_round as administration_period,
        completion_date as test_date,
        `start_date`,
        _dbt_source_project,

        relative_placement as proficiency_level,
        domain_name as response_type_description,

        'iready' as score_source,
        'group' as response_type,

        cast(scale_score as numeric) as scale_score,
        cast(null as numeric) as national_percentile,

        -- Same threshold stg_iready__diagnostic_results applies at subject
        -- level (overall_relative_placement_int >= 4). No per-domain ordinal
        -- column exists upstream, so the two at-or-above labels are tested
        -- directly. See issue #4708 follow-up 2 -- unguarded label vocabulary.
        relative_placement
        in ('Early On Grade Level', 'Mid or Above Grade Level') as is_mastery,
    from {{ ref("int_iready__domain_unpivot") }}
    where
        completion_date is not null
        and _dbt_source_project is not null
        and relative_placement != 'Not Assessed'
),
```

`national_percentile` is explicitly NULL — i-Ready publishes percentiles only at
subject level. The new `placement` column from #4706 is not consumed: it is an
absolute rather than grade-relative scale and would need its own fact column.

#### Dedupe partition must gain the discriminator

This is the change most likely to be missed, and it fails silently.
`iready_scores` applies `dbt_utils.deduplicate` partitioned by
`(_dbt_source_project, student_number, administration_period, module_code, test_date)`.
Because domain rows deliberately share `module_code` with the subject-level
anchor, all 14 domains plus the anchor collapse into a single surviving row
unless `response_type_description` joins the partition key:

```sql
iready_scores as (
    {{
        dbt_utils.deduplicate(
            relation="iready_all_raw",
            partition_by="""
                _dbt_source_project,
                student_number,
                administration_period,
                module_code,
                response_type_description,
                test_date
            """,
            order_by="start_date desc, scale_score desc, academic_year desc",
        )
    }}
),
```

`iready_all_raw` unions `iready_scores_raw` (anchor) and
`iready_domain_scores_raw`. NULL partitions cleanly for anchor rows, so the
existing fiscal-year re-pull dedupe semantics (documented in the CTE's
`TODO(#4387)` comment) are preserved per domain rather than weakened.

`star_scores` and its dedupe are untouched.

### Surrogate key

The shared vendor-branch `assessment_score_key` hashes
`(score_source, _dbt_source_project, student_number, academic_year, administration_period, module_code, test_date)`.
Since `module_code` is now a constant for DIBELS and shared across domains for
i-Ready, that list no longer discriminates: summary and breakdown rows would
collide on one PK. Append `response_type_description` as the eighth and last
input — position matters, since the macro hashes an ordered concatenation.

`generate_surrogate_key` coerces NULL to a deterministic placeholder, so anchor
rows hash consistently — no null-wrap, and per repo convention no `not_null`
test is added on the key itself (the existing `unique` and `not_null` tests on
the PK stay and are the real proof the discriminator suffices).

#### Consumer blast radius

Per the marts hash-change discipline, every consumer was checked:

- **No dbt model reads this fact.** The only `ref()` is
  `models/exposures/cube.yml`. `fct_assessment_scores_student_scoped` is a
  sibling that builds its own `assessment_score_key` from `int_assessments__*`
  models; it is unaffected.
- **Cube uses the column only as a `primary_key` dimension** — never a join key,
  never in a pre-aggregation dimension list. `count_scores` is a plain
  `type: count`. Changing key values is invisible to Cube queries.
- **No mart declares an FK to this fact.**

The key **value** therefore changes for every vendor row, including STAR rows
that gain no data, with no consumer impact. This is expected, not a defect —
called out here so review does not read it as one.

The model is `materialized: table` (per the #4464 Cube-performance exception),
so the rebuild is a full CTAS with no incremental-merge duplicate risk.

### Cube and documentation

No new Cube members are required. `response_type` and
`response_type_description` are already exposed on `student_assessment_scores`
and `student_assessment_scores_view`, and `proficiency_rollup` already includes
all three response-type dimensions — so new rows enter the existing
pre-aggregation automatically. Because `module_code` stays anchored, the
rollup's `assessment_key IS NOT NULL` measure filter passes. Rollup cardinality
grows; its partitioning and build range are unchanged.

Documentation is a required deliverable, because this change redefines an
existing metric rather than only adding a new capability. `pct_proficient` is
documented as the source-agnostic headline metric; a query filtering only
`assessment_type = 'dibels'` or `'iready'` currently returns summary-only
proficiency and afterwards blends summary and breakdown rows unless
`response_type notSet` is added. `count_scores` and `avg_scale_score` shift the
same way. The Cube MCP knowledge docs currently assert these sources are
summary-only, which would actively steer the chat agent away from the filter it
now needs.

| File                                 | Change                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| `fct_..._enrollment_scoped.yml`      | Model description (DIBELS Composite to Composite plus subtests); `response_type` and `response_type_description` column descriptions |
| `student_assessment_scores.yml`      | The four `response_type*` dimension descriptions; `scale_score` (now null for placement-only i-Ready domain rows)                    |
| `student_assessment_scores_view.yml` | View description clause asserting the breakdown is Illuminate only                                                                   |
| `assessment-cube-reference.md`       | Global `response_type` guidance plus the i-Ready and DIBELS section lines asserting summary-only; add per-source filter guidance     |

`response_type_code` and `response_type_root_description` need only a scope
clarification — they remain NULL for both sources.

## Validation

- **Adding `illuminate_subject` breaks the unit test #4709 shipped.**
  `unit_iready_domain_unpivot_placement_scale_score` enumerates every output
  column across 12 `expect` rows, and dbt builds them as `UNION ALL` with no
  null-fill — so the new column must be added to the `given` SQL block and to
  all 12 rows in the same commit, or the test fails on mismatched column counts.
- `unique` and `not_null` on `assessment_score_key` must pass — this is the
  proof `response_type_description` is a sufficient discriminator.
- Row-count assertion in the PR body: the count of rows where
  `response_type is null` must be **unchanged**. A move there means the
  `module_code` re-anchoring altered summary rows, which it must not.
- FK population check per the marts convention: `assessment_administration_key`
  and `assessment_key` must be non-null at the same rate on breakdown rows as on
  summary rows. A null-rate gap means the anchoring failed and orphans were
  created.
- i-Ready domain row count post-filter should reconcile against the merged
  model's output. Re-verified against prod after #4709: of 4,343,808 raw
  domain-column tuples, 2,708,776 carry no `relative_placement` (domain not
  applicable) and are dropped by the model's own inclusion rule, so
  `int_iready__domain_unpivot` emits **1,635,032** rows. Of those, 62,174 are
  `Not Assessed`, leaving **1,572,858** eligible for the fact before enrollment
  scoping. Note that prod had not yet rematerialized the model at the time of
  writing, so these counts were computed by replaying the merged inclusion rule
  against `int_iready__diagnostic_results`; re-confirm against the rebuilt table
  before relying on them.

## Out of scope

- DIBELS progress-monitoring rows.
- State-assessment subclaim or strand breakdowns.
- Unifying `response_type` across all sources.
- Domain-level `national_percentile`.
- A uniqueness test on `int_iready__domain_unpivot` — still absent after #4709,
  which added a unit test but no `data_tests:` block. Pre-existing gap, deferred
  there and here.
- Consuming i-Ready's absolute `placement` column.

Follow-up items for a data engineer, including the unguarded i-Ready label
vocabulary and the saved-consumer audit, are enumerated on
[#4708](https://github.com/TEAMSchools/teamster/issues/4708).
