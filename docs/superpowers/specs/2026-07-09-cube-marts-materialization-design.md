# Cube marts materialization (#4333) — design

## Problem

Cube MCP/REST queries against the assessment cubes intermittently time out cold.
Root cause is performance, not correctness: the mart fact
`fct_assessment_scores_enrollment_scoped` and every dimension it joins are
**views** (`type=2`), re-expanded on every query. The #4298 repro
(`count_scores` by `academic_year`, filter `module_code = QA1`) runs 47–73 s
cold (~2.85 GB scanned, `cache_hit: false`); a fresh reproduction on the
security-redesign branch measured `student_assessment_scores_summary` at
14,171,841 scores in **65.5 s** over the SQL API — past the MCP server's
`TIMEOUT_SECONDS = 55` poll deadline. A "successful" retry only works because
the first attempt warmed Cube's cache.

**65.5 s is the before-number to beat.**

## Scope

The 75 marts in `cube.yml`'s `cube_semantic_layer.depends_on` (the exposure at
`src/dbt/kipptaf/models/exposures/cube.yml`). Cube reads only these.

This is PR #1 of a stacked pair. It lands after the security-redesign PR (#4269)
and is branched from it; retarget to `main` when #4269 merges. The Tesseract
snapshot migration (#4214) is a separate later cycle.

## Sizing (measured)

Output row counts and full-build input scans of the candidate large facts:

| Fact                                      | Rows  | Build scan             |
| ----------------------------------------- | ----- | ---------------------- |
| `fct_grades_assignments`                  | 25.3M | (unmeasured — largest) |
| `fct_assessment_scores_enrollment_scoped` | 14.2M | 2.85 GB                |
| `fct_student_attendance_daily`            | 12.8M | 1.1 GB                 |
| `fct_survey_responses`                    | 1.36M | small                  |
| `fct_family_communications`               | 980K  | small                  |
| `fct_grades_term`                         | 262K  | —                      |
| `fct_assessment_scores_student_scoped`    | 66.5K | —                      |

The build scans are modest (~1–1.5¢ per full rebuild at on-demand rates). The
47–73 s cold latency is a **read-path** cost (view re-expansion per query), not
a build cost. This drives the materialization decision below.

## Approach

Three independent, additive layers.

### 1. dbt materialization — the root-cause fix

Flip the `marts:` default in `src/dbt/kipptaf/dbt_project.yml` from the
inherited `view` to `+materialized: table`. Cube then reads static tables
instead of re-expanding view SQL on every query. **This layer alone resolves
#4333.**

Marts inherit `contract: enforced: true` and (currently) `materialized: view`
from `dbt_project.yml`. The change is adding `+materialized: table` under the
`marts:` key; per-model overrides handle the exceptions below.

### 2. Materialization kind — full-refresh tables, not incremental

**Decision: all marts become plain full-refresh `table`s. No incremental in this
cycle.** Rationale:

- The read-latency fix (#4333's actual problem) is fully delivered by view →
  table; incremental is only a build-cost optimization.
- Build scans are cheap, so a full rebuild on the data-change automation
  condition is inexpensive.
- These large facts are watermark-less district `UNION ALL`s with academic-year
  **restatements** (Illuminate re-syncs; NJ/FL state scores land months late). A
  naive `test_date >= max(test_date)` incremental would silently miss restated
  rows. A correct incremental would need `incremental_strategy='merge'` on the
  surrogate PK plus an academic-year lookback — real complexity for little gain
  at these scan sizes.

Incremental is added later **only** to a specific fact whose _measured_ rebuild
time under the automation cadence proves too slow — decided with real numbers,
not row count. If/when needed, the shape is a `merge` on the `<entity>_key` PK
with `is_incremental()` filtered to the current-and-prior academic year (a
`current_academic_year`-based predicate), never a bare `test_date` watermark.

### 3. Cube pre-aggregation — sub-second hot path

Ship/defer decided by the cost/benefit weighing in the measurement section below
(informed by the C-vs-B numbers, not by the 55 s deadline). Add a `rollup`
pre-aggregation on the assessment cube (a second layer, on the now-table mart)
over the additive primitives `count_scores` and `_sum_proficient` for the
recurring standard-level-proficiency-by-demographic pattern.

Shape:

```yaml
pre_aggregations:
  - name: <name>
    measures:
      - count_scores
      - _sum_proficient
    dimensions:
      # hot-path breakdowns AND the RLS scoping keys (see note)
      - <academic_year, module_code, standard, demographics>
      - <region_key, abbreviation>
    time_dimension: test_date_key
    granularity: day
    partition_granularity: month
```

**Critical RLS subtlety.** Pre-aggregations are built globally, with no
`securityContext`. Cube serves a scoped query from a rollup only if the rollup
contains the dimensions the view's `access_policy` `row_level` filter
interpolates. So the rollup's `dimensions` **must include the location/region
scoping keys** (`region_key`, `abbreviation`) alongside the analytic breakdowns
— otherwise scoped (region/school) viewers silently fall back to the raw table
and never hit the pre-agg. Network-scope viewers (no `row_level`) would hit it
either way; the scoping dims make it work for everyone.

Pre-aggregations are defined on the cube, not the view (Cube convention).

## Wrinkles (decided fallbacks)

- **FK constraints on table marts require the referenced dims to be
  tables-with-PKs (discovered in execution).** When a fact/dim is materialized
  as a table, its `foreign_key` constraints render into `CREATE TABLE` DDL, and
  BigQuery rejects an FK whose referenced table lacks a `primary_key` constraint
  — even for unenforced FKs (`... does not have Primary Key constraints`). A
  referenced dim that is still a view has no PK, so the FK DDL fails. Therefore
  the flip cannot be applied to one fact in isolation: it must land atomically
  across all marts (one `dbt_project.yml` change marks every mart
  `state:modified`, so CI/prod build the whole DAG together) and build in
  dependency order (dims before facts). 60 of the marts carry FK constraints.
  `dim_staff_reporting_chain` is the only constraint-carrying mart with no PK
  constraint, but nothing FKs to it (read only by `cube.js`), so it is not an FK
  target.

- **`dim_staff_reporting_chain` is `WITH RECURSIVE`**
  (`contract: enforced: false`) — **verified in execution: it builds cleanly as
  a table** (`CREATE TABLE AS WITH RECURSIVE`, 8.1k rows). The feared
  subquery-wrap failure did not occur; no view override is needed.

- **`warn_unenforced: false` sweep.** A `config: materialized: table` mart
  renders `constraints:` into `CREATE TABLE` DDL. Every table-mart PK constraint
  needs `warn_unenforced: false` (not just `warn_unsupported: false`) to clear
  the parse warning (per `marts/CLAUDE.md`). Sweep every mart's `primary_key`
  constraint.

- **view → table conversion needs a drop.** `create or replace table` does not
  drop a pre-existing view at the same path (and vice versa). Ship with a
  post-merge `dbt build --select <changed marts> --full-refresh`, or an explicit
  drop, so the conversion doesn't silently keep serving the stale relation (per
  `src/dbt/CLAUDE.md`).

- **Dagster cost absorption.** Table marts now rebuild on the data-change
  automation condition (views did not). Confirm the
  `kipptaf__automation_condition_sensor` wiring absorbs the added rebuild load —
  75 marts moving from view (never rebuilt) to table (rebuilt on upstream data
  change).

## Sequence

1. **Spike A** — materialize only `fct_assessment_scores_enrollment_scoped` as a
   table in a dev schema, re-run the #4298 repro (`count_scores` by
   `academic_year`, `module_code = QA1`) over the SQL API. Confirm cold latency
   drops under 55 s from the 65.5 s baseline. Validates the approach before the
   full sweep.
2. **The pass** — flip the `marts:` default to `table`; `warn_unenforced: false`
   sweep; verify the `WITH RECURSIVE` model; add the assessment pre-aggregation.
   Do the assessment fact first (acute fix + approach validation), then the
   rest.
3. **Validate over the SQL API** — #4298 repro < 55 s; assessment queries stop
   timing out. Testing setup per `src/cube/CLAUDE.md` "Testing row-level
   security locally" and `docs/guides/cube.md` (SQL API via `psycopg2`, connect
   as the viewer email; the branch reworks `dim_staff_cube_access` /
   `dim_staff_reporting_chain`, so temporarily redirect those reads +
   `loadUniverses`' department query to `zz_<user>_kipptaf_marts` to see live
   data — uncommittable scaffold, revert before commit).

## Performance measurement (A/B/C)

Pre-aggregations never block or change query results — an unmatched query
transparently falls back to the underlying table (same answer, slower). So the
pre-agg layer is optional acceleration, and whether to ship it is a cost/benefit
judgment, **not** an automatic pass/fail on the 55 s deadline (clearing 55 s is
the floor, not the bar). The measurement below makes both sides concrete.

Measure the #4298 repro (`count_scores` by `academic_year`, `module_code = QA1`)
in three states over the SQL API:

| Scenario                | State                         | Cold (measured) |
| ----------------------- | ----------------------------- | --------------- |
| **A** — baseline        | marts as views                | 65.5 s          |
| **B** — table only      | marts as tables, no pre-agg   | **19.9 s**      |
| **C** — table + pre-agg | tables + `proficiency_rollup` | **~0.2 s**      |

Measured over the SQL API (local dev server, `psycopg2`, network-scope viewer).
B clears the 55 s deadline (3.3× over A). C is a confirmed rollup hit (~100×
over B; distinct cache-cold queries by subject / demographic / region all
returned in 0.2 s), with a one-time ~56 s rollup build per refresh. **Decision:
ship C** — the ~100× cold-latency win plus per-query scan elimination outweighs
the daily rebuild and dimension-sync maintenance. The **C vs B** delta answers
"how much does the pre-agg buy over just tables."

### Cost/benefit of the pre-agg layer

The decision weighs these, informed by the measurement plus two usage inputs
(hot-path query frequency; the fact's row-growth trajectory):

Benefits:

- **Latency (C vs B).** A rollup hit is typically sub-second even when the table
  clears 55 s — the difference between "the MCP tolerates it" and "an analyst
  iterates interactively."
- **Per-query scan reduction × frequency.** A hit reads a tiny aggregated table
  instead of scanning the fact; `scan_saved × runs/day` is recurring BQ cost
  avoided. Often the largest number, and invisible in a single-query latency
  test — so record hot-path frequency.
- **Concurrency + reliability headroom.** Lighter queries free BQ slots and cut
  timeout risk under load.
- **Growth headroom.** The fact is 14.2M rows and climbing; table-only latency
  degrades as it grows, a coarse-grain rollup far less — the advantage widens
  over time.

Costs:

- **Refresh compute + cadence.** The rollup must be kept fresh (scheduled /
  `refresh_key` rebuild). Partitioned refresh limits this to recent partitions,
  but it is recurring scan.
- **Operational surface.** Pre-agg storage, refresh scheduling, and monitoring
  in Cube Cloud.
- **Maintenance coupling (the real ongoing cost).** The rollup's dimension set
  must track how analysts group/filter AND the RLS scoping keys. Add a breakdown
  or scoping dim and forget the rollup, and it **silently stops matching** —
  queries fall back to the fact with no error.

Methodology (so the numbers are trustworthy):

- **Measure cold.** Cube caches results; the issue's "retry works" is a warmed
  cache. Control for it (cold each run); report warm separately as
  informational.
- **Pre-build the rollup before timing C.** The first query against an unbuilt
  pre-agg pays the build cost — not query latency. Report rollup build time
  separately.
- **Confirm the hit.** Inspect the compiled SQL — a matched query reads the
  rollup table (`..._pre_aggregations.*`), not the fact. If it still reads the
  fact, the pre-agg did not match and the C number is meaningless.
- **Median of 3 runs** per scenario, to smooth BigQuery straggler variance.
- Capture BigQuery `total_bytes_processed` + `total_slot_ms` alongside
  wall-clock, so the scan reduction is visible, not just latency.

Make the ship/defer call by weighing the cost/benefit above with these numbers
in hand — not by whether B alone happens to clear 55 s.

## Out of scope

- Tesseract snapshot `_eop` migration and the `queryRewrite` snapshot-block
  removal (#4214, next cycle).
- Incremental materialization (deferred; added later only where measured).

## Validation / success criteria

- The #4298 repro runs < 55 s cold over the SQL API (from 65.5 s).
- The A/B/C measurement table is produced; the C-vs-B latency + scan delta,
  hot-path query frequency, and the pre-agg cost/benefit are characterized so
  the ship/defer decision is made on the tradeoff (not on the 55 s deadline).
- Assessment MCP queries stop intermittently timing out.
- `dbt build` of the changed marts is green; contract + uniqueness tests pass;
  no new `warn_unenforced` parse warnings.
- `dim_staff_reporting_chain` either materializes cleanly as a table or is
  documented as a deliberate view override.
- Cube RLS still enforces correctly (viewer matrix over the SQL API) — the
  materialization change must not alter access behavior.
