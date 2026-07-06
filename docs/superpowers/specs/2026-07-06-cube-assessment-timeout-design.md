# Fix the assessment-cube query timeout (materialize fact + pre-aggregation)

Issue: [#4333](https://github.com/TEAMSchools/teamster/issues/4333). Refs
[#4298](https://github.com/TEAMSchools/teamster/issues/4298),
[#4299](https://github.com/TEAMSchools/teamster/pull/4299).

## Problem

Cube MCP queries against the assessment cubes intermittently time out at ~55s.
The working-group logs bundled this with the NULL `academic_year` bug, but they
are two separate problems:

- **Correctness** (NULL `academic_year` / zero-row year filters) — fixed by
  #4299's timezone-immune join rewrite. Confirmed working: the compiled join is
  now `dates.date_key = ...administered_date_key` (no `convertTz`) and returns
  correct years (AY2025 = 236,089).
- **Performance** (the 55s timeout) — never in #4299's scope; #4298 explicitly
  deferred it ("revisit separately if timeouts persist"). This spec addresses
  it.

## Root cause

The mart fact and every dimension it joins are unmaterialized **views**,
re-expanded from base data on every query. Only `dim_dates` is a table.

Measured against the #4298 repro
(`student_assessment_scores_summary.count_scores` by `academic_year`, filter
`module_code = QA1`), both cold runs `cache_hit: false`:

| Run          | Elapsed | Bytes   | Slot-ms |
| ------------ | ------- | ------- | ------- |
| Raw BigQuery | 46.9s   | 2.95 GB | 6.98M   |
| Cube `/load` | 73.5s   | 2.95 GB | 7.40M   |

The MCP server's `TIMEOUT_SECONDS = 55` (`src/cube/mcp/server.py`) doubles as
the poll deadline and sits **inside** the 47-73s cold-execution band. So the
query intermittently exceeds it; a retry appears to succeed only because the
first attempt warmed Cube's cache. There are **zero Cube pre-aggregations**
(`preAggregations: []` in the compiled plan), so every cold query pays full
view-expansion cost.

The dominant cost is `fct_assessment_scores_enrollment_scoped` — a union of
internal Illuminate + NJ + FL assessments, each INNER-joined to resolver and
response-rollup intermediates. `dim_dates.date_key` is unique (2.9M rows = daily
dates to year 9999 for SCD2 sentinels), so the join does not fan out; the
2.9M-row date table is not the driver.

## Goals

- The #4298 repro and the kickoff standard-level query return reliably under the
  55s MCP deadline, with real margin — target **< 30s cold**.
- The recurring standard-level-proficiency-by-demographic query returns in **low
  single-digit seconds** via a pre-aggregation.
- No change to query results (same numbers), access policies, or PII posture.

## Non-goals

- The attendance and enrollment cubes. They share the mart-as-view pattern but
  are not currently timing out (the ADA calibration query returned in-session).
  Verify separately; do not materialize them here.
- Raising or reworking the MCP poll deadline. Noted as optional hardening below,
  not part of this fix.
- Any change to the #4299 correctness fix, which is confirmed working.

## Design

Two phases, one spec. Phase 1 is the root-cause fix and is independently
shippable; Phase 2 is a targeted accelerator for a known-recurring query shape.

### Phase 1 — Materialize the fact

1. Set `config.materialized: table` on `fct_assessment_scores_enrollment_scoped`
   in its properties YAML
   (`src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`).
   This follows the sanctioned `dim_dates` table exception to the marts-are-view
   default. It collapses the 3-source union + resolver joins into a precomputed
   scan that every downstream query (Cube and Tableau, summary and detail and
   ad-hoc) reads directly.

2. **Constraint DDL.** A table mart renders `constraints:` into `CREATE TABLE`
   DDL, so add `warn_unenforced: false` to the `primary_key` constraint (it
   currently carries only `warn_unsupported: false`) and review the three
   `foreign_key` constraints (`assessment_administration_key`,
   `student_section_enrollment_key`, `test_date_key`) for the same, to clear
   parse warnings.

3. **Deploy safety.** `create or replace table` does not drop a pre-existing
   view at the same path, so the stale view can keep serving. Ship the
   conversion with a one-time `--full-refresh` after merge (or an explicit
   `DROP VIEW IF EXISTS` at deploy time), per `src/dbt/CLAUDE.md` ->
   "Table->view materialization conversion needs a drop" (the inverse applies
   here).

4. **Refresh cadence.** Table marts rematerialize under Dagster's data-change
   automation condition; view marts do not. Materializing the fact means it
   refreshes automatically when its upstreams change — no schedule to add.

5. **Measurement gate.** Before assuming the fact alone suffices:
   - Build the fact as a table into a dev schema:
     `uv run dbt run --select fct_assessment_scores_enrollment_scoped --project-dir src/dbt/kipptaf --target dev`
     (creates
     `zz_<username>_kipptaf_marts.fct_assessment_scores_enrollment_scoped`).
   - Re-run the compiled repro query with the fact reference pointed at the
     `zz_*` table (dims stay prod views) and read elapsed time from
     `INFORMATION_SCHEMA.JOBS_BY_PROJECT`.
   - If not comfortably under target, materialize the next-heaviest dimension
     view(s) — most likely `dim_student_enrollments` and
     `dim_student_section_enrollments` — and re-measure. Materialize only what
     the measurement shows is needed; do not pre-emptively convert all seven.

### Phase 2 — Standard-level pre-aggregation

The `student_assessment_scores` cube already exposes the additive primitives a
rollup needs (`count_scores` as `type: count`; `_sum_proficient` as `type: sum`
of `IF(is_mastery, 1, 0)`; `pct_proficient` derived as
`1.0 * _sum_proficient / NULLIF(count_scores, 0)`), and its descriptions already
declare them pre-aggregation-ready.

1. Define a `pre_aggregations` rollup on the `student_assessment_scores` cube at
   grain:
   - **Measures:** `count_scores`, `_sum_proficient`.
   - **Dimensions:** `response_type_code`, `response_type`, `is_iep`,
     `grade_level`, `discipline`, `region`, `module_code`, `academic_year`.

   `pct_proficient` recomputes exactly from the two rolled-up primitives, so a
   query matching this grain (the kickoff standard-level equity cut, and its
   recurring siblings) is served from the rollup in milliseconds. Exact Cube
   member paths and the joins that must be included in the rollup are resolved
   during implementation against the cube/view YAML.

2. **Refresh backend — open decision.** Cube pre-aggregations build either into
   Cube Store or into the warehouse (`external: false`). There is no pre-agg
   precedent in this repo, so pick the backend, `refreshKey`, and partitioning
   (e.g. partition by `academic_year`) in implementation. With Phase 1 done,
   each refresh reads the materialized fact, so the refresh job is cheap.

## Testing and validation

- **dbt.** The existing `unique` / `not_null` / `relationships` /
  `accepted_values` tests carry over to the table build; confirm they pass.
  Confirm row-count parity between the pre-change view and the post-change table
  (same numbers).
- **Cube correctness.** Re-run the #4298 repro and the kickoff query via `/sql`
  (the join predicate must be unchanged from #4299) and via `/load` (results
  unchanged).
- **Cube latency.** Confirm the repro/kickoff `/load` returns under target cold,
  and that a rollup-matching query is served from the pre-aggregation — verify
  the compiled SQL references the rollup table, not the fact.

## Rollout and ordering

1. Phase 1 (dbt) merges first. Post-merge: one-time `--full-refresh` of the
   fact, then confirm via Dagster/BigQuery the table materialized.
2. Re-measure latency in prod; decide from the measurement whether any dimension
   views also need materializing (fold into the same PR if the branch is still
   open, else a follow-up).
3. Phase 2 (Cube) — add the pre-aggregation once the fact is a table so refresh
   is cheap. Cube Cloud redeploys the model on merge to `main`.

## Risks and mitigations

- **Materialized fact still exceeds target.** Mitigated by the measurement gate
  and the dimension-materialization fallback.
- **Convention deviation (marts are views).** Justified by the measured timeout
  and the `dim_dates` precedent; called out explicitly here for review.
- **view->table conversion serves a stale view.** Mitigated by the one-time
  `--full-refresh` / explicit drop on deploy.
- **Pre-aggregation only helps enumerated cuts.** Accepted: Phase 1
  materialization is the uniform foundation for all other (including
  not-yet-discovered) ad-hoc cuts; the rollup accelerates the one known
  recurring shape.

## Optional hardening (not in scope)

Decouple the MCP server's HTTP timeout from its poll deadline and add a single
retry on a `Continue wait` timeout (the query often completes on Cube's side and
caches moments later). Cheap insurance against residual cold-start variance;
track separately if wanted.

## References

- `src/dbt/kipptaf/models/marts/CLAUDE.md` — table-mart constraint flags,
  materialization overrides.
- `src/dbt/CLAUDE.md` — materialization-conversion drop requirement,
  table-vs-view refresh cadence.
- `src/cube/CLAUDE.md` — cube authoring, pre-aggregation notes.
- `src/cube/model/cubes/student_assessments/student_assessment_scores.yml` —
  additive measure primitives.
