# Split the resolver's score union into `int_assessments__score_anchors`

Design for [#5261](https://github.com/TEAMSchools/teamster/issues/5261). Follows
#5252. Parent: #5212.

## Problem

`int_assessments__resolved_section_enrollments` costs 15.15 slot hours over 7
days in prod (36 rebuilds, 25.3 slot-minutes each) while scanning 0.3 GiB per
build. The #5252 macro rewrites inside it cost 3.4 slot-minutes per build
combined, so the macro was never the driver.

The measurement on #5261 (`unnest(job_stages)` over every prod
`CREATE_TABLE_AS_SELECT` for the node, 2026-09-07 to 2026-09-14) attributes the
cost to two things:

| Stage bucket (`records_read`) | Stages | Slot-min per build | Share |
| ----------------------------- | -----: | -----------------: | ----: |
| >= 10M                        |      2 |               16.4 |   66% |
| 1M to 10M                     |      7 |                3.4 |   14% |
| 100k to 1M                    |     26 |                0.6 |    2% |
| < 100k                        |    115 |                4.1 |   17% |

1. **Broadcast joins to `int_assessments__course_enrollments`.** Both candidate
   joins run as `INNER HASH JOIN EACH WITH ALL`. The tier-1 stage reads 348.6M
   records to write 2.68M rows across 424 parallel inputs; 424 x 706,098
   inventory rows = 299M of that read is the broadcast copy.
2. **The `scores` CTE is inlined three times.** It is referenced from
   `candidates_subject`, `resolved_subject_keys` (through `candidates_subject`
   again), and `scores_unresolved`. BigQuery inlines a CTE per reference, and
   two of the union's inputs are views with deep plans of their own:
   `int_amplify__all_assessments` is 65 stages standalone and
   `int_assessments__assessments_canonical` is 23. That is where the 154-stage
   plan and the 424 parallel inputs come from.

Both point at the same root: the union is recomputed per reference. Reading it
once from a table removes the small-stage tax outright and shrinks the parallel
input count that multiplies the broadcast.

## Decision

Split the union into its own table model. Materializing the two deep views was
considered and set aside: it touches 22 kipptaf consumers and needs a
view-to-table drop plus a cadence check for each. It stays available as a
follow-up if the split alone does not clear the bar.

## Design

### New model: `int_assessments__score_anchors`

`src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`.
`materialized: table`,
`automation_condition.cron_schedule: 0 0,10,13,15,17 * * *` (the tick shared by
`int_assessments__scaffold`, `int_assessments__course_enrollments`, the
resolver, and `fct_assessment_scores_enrollment_scoped`, so
`~any_deps_in_progress` orders it before the resolver in the same pass).

It takes everything the resolver does today up to `scores_mapped`, unchanged:

- `internal_anchored` (scaffold x canonical, `row_number()` on earliest
  `administered_date`) and `internal_scores`
- `state_nj_scores`, `state_fl_scores`, `iready_scores`, `star_scores`,
  `dibels_scores`, with their existing filters and inline comments
- the six-way `scores` union
- `score_grain_key` via `dbt_utils.generate_surrogate_key` over the same seven
  inputs in the same order

Two changes from the current CTE chain:

- `course_subject` is dropped. It is `subject_area as course_subject`, a pure
  alias; the resolver joins on `subject_area` directly.
- The final select is `select distinct` over the nine columns, annotated
  `-- grain projection, not dup-masking`. Every projected column is part of the
  grain, so byte-identical tuples coalesce and nothing else does.

Columns, in order: `powerschool_student_number`, `canonical_assessment_id`,
`academic_year`, `administration_period`, `subject_area`, `_dbt_source_project`,
`anchor_date`, `source_type`, `score_grain_key`.

Uniqueness test: `dbt_utils.unique_combination_of_columns` over the seven grain
columns plus `anchor_date`. Prod, measured 2026-09-14 on the current union:

| `source_type` |      Rows | Distinct grain | Distinct grain + `anchor_date` |
| ------------- | --------: | -------------: | -----------------------------: |
| internal      | 2,262,873 |      2,262,873 |                      2,262,873 |
| state_nj      |    71,996 |         71,996 |                         71,996 |
| state_fl      |    20,285 |         20,285 |                         20,285 |
| iready        |   274,172 |        257,696 |                        264,787 |
| star          |     8,128 |          7,927 |                          7,965 |
| dibels        |    62,485 |         62,483 |                         62,485 |

The gap between rows and distinct grain + date (iready 9,385, star 163) is
exact-duplicate tuples: the union's eight columns are the key, so two rows that
agree on all of them are the same row. Collapsing them cannot change the
resolver's output, because identical candidate rows rank identically in
`all_candidates_ranked`. The gap between distinct grain and distinct grain +
date (iready retests on different days, star, dibels) is real and is kept: each
`anchor_date` is a separate chance at an enrollment window.

`score_grain_key` is not the uniqueness key on its own, and the properties yml
says so, so nobody adds a `unique` test to it later.

Also carries `accepted_values` on `source_type` (the same six values the
resolver tests today) and `not_null` on `anchor_date`,
`powerschool_student_number` and `_dbt_source_project`, which the branch filters
already guarantee.

### Resolver: `int_assessments__resolved_section_enrollments`

Everything before `candidates_subject` is deleted. `candidates_subject` and
`scores_unresolved` read `{{ ref("int_assessments__score_anchors") }}` instead
of `scores_mapped`, and the tier-1 join predicate becomes
`s.subject_area = ce.illuminate_subject_area`. `resolved_subject_keys`,
`candidates_homeroom`, `all_candidates`, `all_candidates_ranked`, `resolved`,
and the final select are unchanged.

Output columns, types, and grain are unchanged, so
`fct_assessment_scores_enrollment_scoped`, the singular tests
`int_assessments__resolved_section_enrollments__unique_per_score` and
`fct_assessment_scores_enrollment_scoped__term_covers_assessment_date`, and
every column description in the resolver's properties yml stay as they are. The
model `description` gets one sentence saying the score union now comes from
`int_assessments__score_anchors`.

### Unit tests

The resolver's five unit tests each mock eight upstream refs (`scaffold`,
`canonical`, `course_enrollments`, and the five external sources). Each is
rewritten to mock two: `int_assessments__score_anchors` rows carrying the
`score_grain_key` the test needs, and `int_assessments__course_enrollments`. The
expected rows do not change. `score_grain_key` in the fixtures is any distinct
string per score; the resolver only compares it for equality.

The internal anchoring rule (earliest `administered_date` across the canonical's
scaffold rows wins, replacements and non-internal rows excluded) leaves the
resolver, so it gets one unit test on `int_assessments__score_anchors`: two
scaffold rows for the same (student, canonical, project) with different
administered dates, expect one output row on the earlier date.

### Verification

1. **Value-level proof, before the PR is marked ready.** Run the current
   compiled resolver SQL and the new chain (new model SQL as a CTE feeding the
   new resolver SQL) against the same prod snapshot in one query. Full outer
   join on the seven-column grain (`format('%T|...')`, NULL-safe), compare
   `to_json_string` over every output column in properties order. Expect 0
   only-in-old, 0 only-in-new, 0 differing. Record the counts in the PR.
2. **Local build.**
   `uv run dbt build --select int_assessments__score_anchors+ --project-dir <worktree>/src/dbt/kipptaf`
   per `dbt-local-dev`, including the six unit tests and both singular tests.
3. **Cost, 7 days after merge.** `JOBS_BY_PROJECT` slot hours for
   `int_assessments__score_anchors` plus
   `int_assessments__resolved_section_enrollments` combined, same query shape as
   the #5261 measurement. Baseline is 15.15.

### Done when

- Combined 7-day slot hours for the two models are under 10 (the #5212 bar).
- The value-level proof recorded 0 / 0 / 0.
- The five rewritten unit tests and the one new one pass in CI.

If the combined cost lands above 10 because the broadcast join is still
expensive with fewer parallel inputs, that is a new issue under #5212 naming the
two views, not a widening of this one.

## Out of scope

- Materializing `int_amplify__all_assessments` or
  `int_assessments__assessments_canonical`.
- Any change to `fct_assessment_scores_enrollment_scoped`. Its 13.65 slot hours
  are 13.5M output rows times five builds a day, and the cadence is the #4821
  decision.
- Any new consumer of `int_assessments__score_anchors`. It exists to feed the
  resolver.
