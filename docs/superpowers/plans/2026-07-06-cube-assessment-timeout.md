# Assessment-Cube Timeout Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the assessment-cube Cube MCP queries from timing out by
materializing the heavy fact and adding a standard-level pre-aggregation.

**Architecture:** Phase 1 flips `fct_assessment_scores_enrollment_scoped` from a
view to a table (the `dim_dates` precedent), collapsing the per-query 3-source
union + resolver-join expansion into a precomputed scan. A measurement gate
decides whether the heaviest dimension views also need materializing. Phase 2
adds a Cube `rollup` pre-aggregation on the additive proficiency primitives for
the recurring standard-level equity query. Spec:
[docs/superpowers/specs/2026-07-06-cube-assessment-timeout-design.md](2026-07-06-cube-assessment-timeout-design.md).

**Tech Stack:** dbt (BigQuery, contract-enforced marts), Cube semantic layer
(YAML data model, Cube Cloud), BigQuery MCP for measurement.

## Global Constraints

- **`--target prod` dbt builds are classifier-blocked for Claude** — hand prod
  builds / `--full-refresh` to the user. Claude runs `--target dev` builds only.
- **No manual Cube deploy** — Cube Cloud redeploys the model on merge to `main`.
  Pre-merge Cube validation is via Cube Cloud Dev Mode (a UI action → user) or
  the local `Cube: Dev Server` VS Code task (long-running → user).
- **Marts are `materialized: view` by default** (`dbt_project.yml`); `dim_dates`
  is the sanctioned table exception. A `config.materialized: table` mart renders
  `constraints:` into CREATE TABLE DDL — set `warn_unenforced: false` on the
  `primary_key` constraint (and FK constraints if dbt warns).
- **view→table conversion needs a drop** — `create or replace table` does not
  drop a pre-existing view; the prod rollout must `--full-refresh` (or
  `DROP VIEW`) once.
- **`--state` is relative to `--project-dir`** — use `--state target/prod`, not
  a repo-root path.
- **No results change** — same numbers, access policies, and PII posture as
  today.
- Work is on branch `cristinabaldor/fix/claude-cube-assessment-timeout` (Refs
  #4333).

---

## Open decisions (reviewer input needed)

Two decisions need a reviewer with more warehouse/Cube context before execution
continues. Both were surfaced during execution (Decision 1 blocks Task 1; the
plan author did not have enough context to choose either).

### Decision 1 — Fact materialization vs FK constraints (blocks Task 1)

**Discovery (during the Task 1 dev build).** Converting the fact to a table
makes dbt render its `foreign_key` constraints into `CREATE TABLE` DDL, and the
build failed:

```text
Table teamster-332318.kipptaf_marts.dim_assessment_administrations
does not have Primary Key constraints
```

BigQuery validates that a table's `foreign_key` constraint references a **table
with a declared primary key**, even when the constraint is `NOT ENFORCED`. Two
of the fact's FK parents (`dim_assessment_administrations`,
`dim_student_section_enrollments`) are views, so BigQuery rejects the DDL.
`dim_dates` succeeded as a table only because it has no FKs — so the `dim_dates`
precedent does not transfer to a fact that carries FKs.

**Options:**

- **Option A (author's recommendation): fact → table, drop its three
  `foreign_key` constraints, keep the three `relationships` data tests.** FK
  constraints on BigQuery are `NOT ENFORCED` (informational only), so dropping
  them costs nothing at query or enforcement time, and the `relationships` tests
  still catch orphans. **Cost:** the generated FK reference diagram
  (`generate_marts_reference.py` reads only `foreign_key` constraints, never
  `relationships` tests) loses the fact's three outgoing edges, and this bends
  the `marts/CLAUDE.md` "declare outgoing FKs on every mart" rule. Mitigate by
  documenting the exception in the model, or by teaching the generator to also
  read `relationships` tests (larger scope). **This convention trade-off is the
  crux of the decision.**
- **Option B: materialize the fact and its FK-referenced dims as tables** so the
  constraints stay valid. This cascades — each newly-materialized dim's own FKs
  then require _its_ parents to be tables-with-PK, propagating through most of
  the star schema (or dropping FKs throughout anyway). Disproportionate for a
  performance fix.
- **Option C: leave the fact a view; materialize its heavy upstream `int_`
  inputs instead.** Sidesteps the FK-DDL issue (intermediates carry no dim FK
  constraints). Less certain to clear the 55s deadline — the fact view still
  does the three-branch union + resolver joins at query time, just over
  precomputed inputs — so it needs measurement, and it spreads materialization
  into the intermediate layer.

**Working-tree state:** clean. The Task 1 subagent's two edits
(`config: materialized: table` + `warn_unenforced: false` on the PK) were
reverted for a clean handoff; the exact edit is preserved in Task 1 Step 1.
Re-apply it if Decision 1 lands on Option A.

**Reviewer question:** which option — and if A, is dropping the FK constraints
(accepting the reference-diagram edge loss and the `marts/CLAUDE.md` deviation)
acceptable?

### Decision 2 — Pre-aggregation storage: Cube Store vs BigQuery

The Task 3 `rollup` must be built and stored somewhere. Cube supports two
backends; the block in Task 3 uses Cube's default (Cube Store). Verified against
Cube docs.

**Option 1 — Cube Store (Cube's default for rollups; `external: true`).** The
refresh worker runs the rollup SQL against BigQuery, unloads results to a GCS
export bucket, and ingests them into Cube Store (Parquet on blob storage).
Matched queries are served from Cube Store.

- _Requires:_ a GCS export bucket configured on the Cube Cloud BigQuery data
  source (`CUBEJS_DB_EXPORT_BUCKET` / Cube Cloud equivalent) and a running
  refresh worker (Cube Cloud manages this).
- _Pros:_ fastest serving (purpose-built columnar store, in-memory-class
  latency); reads never touch BigQuery, so no BQ slot contention or per-query
  scan cost and predictable latency under dashboard concurrency; first-class
  Cube Cloud path with well-supported partitioning, incremental refresh, and
  scheduling.
- _Cons:_ aggregated data is copied **out of BigQuery** into Cube Store, a
  second location outside the warehouse's IAM / VPC-SC / governance. This rollup
  includes indirect identifiers as aggregate counts (`is_iep`, `region_name`,
  `grade_level`, `discipline`); low-n cells could be sensitive, so a
  governance/PII review is needed before demographic aggregates leave the BQ
  boundary. Also adds the export bucket + refresh worker as deployment surface
  (possible Cube Cloud plan/cost implications), and Cube Store is less directly
  inspectable than a warehouse table.

**Option 2 — Keep the pre-agg in BigQuery (`external: false`).** Cube builds the
rollup as a table in a dedicated BigQuery pre-agg schema (e.g.
`prod_pre_aggregations`); matched queries read that table directly from
BigQuery.

- _Requires:_ the Cube BigQuery service account to have write access to a
  dedicated pre-agg dataset.
- _Pros:_ data stays in BigQuery — same IAM, PII controls, VPC-SC, and
  observability as the rest of the warehouse; nothing leaves GCP, fitting the
  repo's "PII stays in the warehouse" posture. No export bucket / Cube Store
  dependency (smaller deployment footprint). The pre-agg table is directly
  queryable in BQ for validation/debugging.
- _Cons:_ reads still go through BigQuery — fast and cheap on a small aggregate
  table, but not Cube-Store-fast, and each read uses BQ slots and incurs a
  (small) scan cost. Less-standard path for `rollup` pre-aggs — Cube documents
  steer toward Cube Store, and `original_sql` is the type designed to live in-DB
  — so expect fewer guardrails. Shares the BQ slot pool with all other workloads
  (concurrency contention under load).

**Author's lean (reviewer to weigh):** given the repo's strong
PII-stays-in-BigQuery posture and that, with the fact materialized, the rollup
is a small aggregate BigQuery serves quickly, **Option 2 (keep in BigQuery)** is
the lower-risk default. Choose **Cube Store** if sub-second latency under real
dashboard concurrency becomes a hard requirement and the governance review
clears aggregated demographic data leaving the warehouse.

---

### Task 1: Materialize the fact as a table

> **BLOCKED pending Open Decision 1.** The concrete edit below assumes the FK
> constraints stay. If Decision 1 lands on Option A, drop the three
> `foreign_key` constraints instead of retaining them; if Option C, this task
> changes to materializing upstream `int_` models. Do not execute until Decision
> 1 is made.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: `kipptaf_marts.fct_assessment_scores_enrollment_scoped` becomes a
  table on prod deploy; a dev copy
  `zz_<dev-schema>_kipptaf_marts.fct_assessment_scores_enrollment_scoped` after
  the dev build in this task, consumed by Task 2's measurement.

- [ ] **Step 1: Add the table materialization and constraint flag**

In the properties YAML, add a model-level `config` block (a mart has none today)
directly under `name:`, and add `warn_unenforced: false` to the existing
`primary_key` constraint.

```yaml
models:
  - name: fct_assessment_scores_enrollment_scoped
    config:
      materialized: table
    description: >-
      Enrollment-scoped assessment score fact table. One row per student x
      assessment x administration. Covers internal Illuminate assessments and
      state assessments (NJSLA, NJGPA, FAST). Each row is linked to an
      assessment administration (via assessment_administration_key) and to the
      student's resolved section enrollment (via student_section_enrollment_key
      and enrollment_resolution).
    columns:
      - name: assessment_score_key
        data_type: string
        description: >-
          Surrogate key. Primary key for this fact table.
        constraints:
          - type: primary_key
            warn_unsupported: false
            warn_unenforced: false
```

Leave every other column and the three `foreign_key` constraints unchanged for
now.

- [ ] **Step 2: Validate the model parses**

Run: `uv run dbt parse --target prod --project-dir src/dbt/kipptaf` Expected:
parses with no error (`--target prod` parse is allowed — no warehouse write).

- [ ] **Step 3: Build the fact into a dev schema and run its tests**

Run:
`uv run dbt build --select fct_assessment_scores_enrollment_scoped --defer --state target/prod --target dev --project-dir src/dbt/kipptaf`

Expected: `PASS` on the model build (creates
`zz_<dev-schema>_kipptaf_marts.fct_assessment_scores_enrollment_scoped` as a
TABLE) and `PASS` on the `unique`, `not_null`, `relationships`, and
`accepted_values` tests. Note the exact `zz_<dev-schema>_kipptaf_marts` relation
name from the log — Task 2 uses it.

- [ ] **Step 4: Check for unenforced-constraint warnings**

Scan the Step 3 output for `unenforced constraint` warnings. The PK is already
handled by Step 1. If any `foreign_key` constraint
(`assessment_administration_key`, `student_section_enrollment_key`,
`test_date_key`) warns, add `warn_unenforced: false` beside its existing
`warn_unsupported: false`, then re-run Step 3 and confirm the warning is gone.
Expected end state: build succeeds with no constraint warnings.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git commit -m "fix(cube): materialize fct_assessment_scores_enrollment_scoped as table

The fact was a view re-expanded on every Cube query (47-73s cold), driving
the assessment-cube timeout. Materialize it (the dim_dates pattern) so
queries read a precomputed scan.

Refs #4333"
```

---

### Task 2: Measure fact-as-table latency and decide on dimensions

**Files:**

- Modify (conditional, only if the gate fails): dimension properties YAMLs under
  `src/dbt/kipptaf/models/marts/dimensions/properties/`.

**Interfaces:**

- Consumes: the dev fact table from Task 1.
- Produces: a go/no-go decision recorded in the task; conditionally, additional
  table-materialized dims.

- [ ] **Step 1: Run the repro query against the dev fact + prod dims**

Substitute the `zz_<dev-schema>_kipptaf_marts` name from Task 1 Step 3 for the
fact table only (all `dim_*` stay `kipptaf_marts`). Run via BigQuery MCP
(`mcp__bigquery__execute_sql`):

```sql
SELECT `dates`.academic_year AS academic_year,
       count(CASE WHEN (`student_assessments`.assessment_key IS NOT NULL)
                   AND (`regions`.region_key IS NOT NULL)
                  THEN `student_assessment_scores`.assessment_score_key END) AS count_scores
FROM kipptaf_marts.fct_assessment_scores_enrollment_scoped AS `student_assessment_scores`
LEFT JOIN kipptaf_marts.dim_assessment_administrations AS `student_assessment_administrations`
  ON `student_assessment_administrations`.assessment_administration_key = `student_assessment_scores`.assessment_administration_key
LEFT JOIN kipptaf_marts.dim_dates AS `dates`
  ON `dates`.date_key = `student_assessment_administrations`.administered_date_key
LEFT JOIN kipptaf_marts.dim_assessments AS `student_assessments`
  ON `student_assessments`.assessment_key = `student_assessment_administrations`.assessment_key
LEFT JOIN kipptaf_marts.dim_student_section_enrollments AS `student_section_enrollments`
  ON `student_section_enrollments`.student_section_enrollment_key = `student_assessment_scores`.student_section_enrollment_key
LEFT JOIN kipptaf_marts.dim_student_enrollments AS `student_school_enrollments`
  ON `student_school_enrollments`.student_enrollment_key = `student_section_enrollments`.student_enrollment_key
LEFT JOIN kipptaf_marts.dim_locations AS `locations`
  ON `locations`.location_key = `student_school_enrollments`.location_key
LEFT JOIN kipptaf_marts.dim_regions AS `regions`
  ON `regions`.region_key = `locations`.region_key
WHERE (`student_assessments`.module_code = 'QA1')
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10000
```

(Replace the first `FROM kipptaf_marts.fct_assessment_scores_enrollment_scoped`
with the `zz_*` table.) Expected: same 9 academic-year rows, AY2025 ≈ 236,089.

- [ ] **Step 2: Read the cold execution time**

Run via BigQuery MCP:

```sql
SELECT job_id,
       TIMESTAMP_DIFF(end_time, creation_time, MILLISECOND) AS elapsed_ms,
       total_bytes_processed, total_slot_ms, cache_hit
FROM `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE)
  AND job_type = 'QUERY'
  AND REGEXP_CONTAINS(query, r'fct_assessment_scores_enrollment_scoped')
  AND cache_hit = FALSE
ORDER BY creation_time DESC
LIMIT 5
```

Expected: `elapsed_ms` for the just-run query. Record it.

- [ ] **Step 3: Decision gate**

- If `elapsed_ms < 30000` (target, well under the 55s deadline): the fact alone
  suffices — skip Steps 4-5 and go to Task 3.
- If `elapsed_ms >= 30000`: proceed to Step 4.

- [ ] **Step 4 (conditional): Materialize the two heaviest dimension views**

Add the same `config: materialized: table` block (Task 1 Step 1 shape, plus
`warn_unenforced: false` on each dim's `primary_key`) to the properties YAML of
`dim_student_enrollments` and `dim_student_section_enrollments`, then build
both:

```bash
uv run dbt build --select dim_student_enrollments dim_student_section_enrollments --defer --state target/prod --target dev --project-dir src/dbt/kipptaf
```

Expected: both build as TABLE, tests PASS. Re-run Steps 1-2 pointing the fact
and these two dims at their `zz_*` tables; confirm `elapsed_ms < 30000`. If it
is still over, stop and report — do not materialize further dims blindly; the
result means the cost is elsewhere and needs re-diagnosis.

- [ ] **Step 5 (conditional): Commit the dimension materialization**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml
git commit -m "fix(cube): materialize heaviest assessment dims as tables

Measurement showed the fact alone did not clear the latency target;
materialize dim_student_enrollments and dim_student_section_enrollments.

Refs #4333"
```

---

### Task 3: Add the standard-level pre-aggregation

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`

**Interfaces:**

- Consumes: the materialized fact (Task 1) so the rollup refresh is cheap.
- Produces: a `rollup` pre-aggregation `standard_proficiency_rollup` that serves
  `pct_proficient` / `count_scores` queries at the standard × demographic grain.

- [ ] **Step 1: Add the pre_aggregations block to the cube**

Append a top-level `pre_aggregations:` key to the `student_assessment_scores`
cube (a sibling of `joins:`, `dimensions:`, `measures:`), using the same
join-path member references the views already use. `count_students` (a
count-distinct) is deliberately excluded — it is not additive and not part of
the targeted pattern.

```yaml
pre_aggregations:
  # First pre-aggregation in the repo. Serves the recurring standard-level
  # proficiency-by-demographic query (#4333). pct_proficient recomputes from
  # the two additive primitives (count_scores, _sum_proficient), so a query
  # whose members are a subset of this grain is served from the rollup.
  # No time_dimension: academic_year is a plain dimension here and state
  # rows have null administration dates, so a time-partitioned rollup would
  # drop them. Refresh is a full rebuild against the materialized fact.
  - name: standard_proficiency_rollup
    type: rollup
    measures:
      - student_assessment_scores.count_scores
      - student_assessment_scores._sum_proficient
    dimensions:
      - student_assessment_scores.response_type_code
      - student_assessment_scores.response_type
      - student_assessment_scores.student_assessment_administrations.student_assessments.module_code
      - student_assessment_scores.student_assessment_administrations.dates.academic_year
      - student_assessment_scores.student_section_enrollments.course_sections.courses.discipline
      - student_assessment_scores.student_section_enrollments.student_school_enrollments.grade_level
      - student_assessment_scores.student_section_enrollments.student_school_enrollments.student_enrollment_status.is_iep
      - student_assessment_scores.student_section_enrollments.student_school_enrollments.locations.regions.region_name
    refresh_key:
      every: 6 hour
```

> **Storage backend is Open Decision 2.** The block above uses Cube's default
> (Cube Store). If the reviewer chooses the in-BigQuery backend, add
> `external: false` to the pre-aggregation. See "Open decisions" above.

- [ ] **Step 2: Trunk-check the changed YAML**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
Expected: no issues (fix any yamllint finding inline).

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/student_assessments/student_assessment_scores.yml
git commit -m "fix(cube): add standard-level proficiency pre-aggregation

Rollup on count_scores/_sum_proficient by standard x demographic so the
recurring equity query is served from the pre-aggregation instead of a cold
fact scan.

Refs #4333"
```

- [ ] **Step 4: Pre-merge Cube validation (hand to user)**

Claude cannot run Cube Cloud Dev Mode (UI) or the long-running local dev server.
Ask the user to either (a) open Cube Cloud → Data Model → Dev Mode, add the
branch, or (b) start the `Cube: Dev Server` VS Code task, then run the kickoff
query (`pct_proficient` + `count_scores` by `response_type_description` ×
`is_iep`, filtered grade 5 / Mathematics / Newark / `response_type = standard` /
QAs / two school years). Confirm the model compiles with the pre-aggregation
present. Full pre-agg-hit + latency verification happens post-merge (Rollout
Step 3), since the rollup only builds in a deployed environment.

---

## Post-merge rollout

These are user / CI actions, in order:

1. **Open the PR** using `.github/pull_request_template.md`; the body references
   `Closes #4333`. Squash merge after dbt Cloud CI + Trunk pass.
2. **Prod fact rebuild (user).** view→table does not auto-drop the view, so once
   after merge run a one-time full refresh of the fact (and any dims from Task 2
   Step 4):
   `dbt build --select fct_assessment_scores_enrollment_scoped --full-refresh --target prod`
   (or Dagster full-refresh). Confirm via BigQuery `kipptaf_marts.__TABLES__`
   that `type = 1` (table) for the fact.
3. **Prod Cube validation (Claude, via the `cube` MCP).** After Cube Cloud
   redeploys and the rollup builds: run the kickoff query with
   `mcp__claude_ai_Cube__sql` and confirm the compiled SQL reads the
   pre-aggregation rollup table (not `fct_assessment_scores_enrollment_scoped`);
   run it with `mcp__claude_ai_Cube__load` and confirm it returns in low
   single-digit seconds. Then re-run the #4298 repro (`count_scores` by
   `academic_year`, `module_code = QA1`) and confirm it returns under target
   cold — this one is served by the materialized fact, not the rollup.

---

## Self-review notes

- Spec coverage: Phase 1 materialization → Task 1; measurement gate + dim
  fallback → Task 2; Phase 2 pre-aggregation → Task 3; testing/rollout → Rollout
  section. Two decisions are unresolved and captured in "Open decisions
  (reviewer input needed)" above: the fact-materialization vs FK-constraint
  conflict (blocks Task 1) and the pre-aggregation storage backend (Cube Store
  vs BigQuery). Rollup partitioning is deferred (no `time_dimension`).
- The optional MCP-deadline hardening in the spec is intentionally not a task
  (out of scope per the spec).
