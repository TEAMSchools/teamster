# Strand-Scores Rollback Baseline

Captured 2026-08-28, ~23:12–23:20 UTC, against **production** BigQuery
(`teamster-332318`), via `uv run dbt show --project-dir src/dbt/kipptaf` against
`kipptaf_marts.*` fully-qualified tables (not `ref()` — this is a production
baseline, not a dev-schema read). All queries are read-only SELECTs; no models
were changed to produce this document.

This is the baseline Task 9 asserts against when verifying a rollback of the
strand-level-scores change.

## Cross-check against known-good values

Before recording these numbers as the baseline, they were compared against
values verified against prod on 2026-08-28 (same day, earlier):

| Metric                        | Known-good |   Captured | Delta |
| ----------------------------- | ---------: | ---------: | ----: |
| Fact total                    | 14,569,177 | 14,569,370 |  +193 |
| `response_type IS NULL` total |  1,441,444 |  1,441,587 |  +143 |
| — illuminate                  |  1,073,422 |  1,073,419 |    -3 |
| — iready                      |    240,749 |    240,833 |   +84 |
| — dibels                      |     57,546 |     57,546 |     0 |
| — star                        |      7,349 |      7,349 |     0 |
| — state_nj_njsla              |     35,123 |     35,096 |   -27 |
| — state_fl_fast               |     17,782 |     17,780 |    -2 |
| — state_nj_njsla_science      |      6,281 |      6,313 |   +32 |
| — state_nj_njgpa              |      2,232 |      2,288 |   +56 |
| — state_fl_science            |        703 |        703 |     0 |
| — state_fl_eoc                |        257 |        260 |    +3 |
| `response_type` = standard    |  8,688,108 |  8,688,150 |   +42 |
| `response_type` = group       |  2,867,069 |  2,867,068 |    -1 |
| `response_type` = overall     |  1,572,556 |  1,572,565 |    +9 |
| `response_type` = NULL        |  1,441,444 |  1,441,587 |  +143 |

**These do not match exactly.** dibels, star, and state_fl_science match to the
row; every other category is off by a small amount (-27 to +84 rows, mixed
direction — not uniform growth), netting to +193 rows on the fact total
(0.0013%). The join structure and category set match exactly (same 13
`(assessment_type, response_type)` combinations, same zero orphans on the FK
join — see below), so this is not a wrong-table or wrong-join situation.

**This was not root-caused before recording.** The most likely explanation is
ordinary intraday movement on a live warehouse — the known-good values were
captured earlier the same day, and Dagster runs assessment ingestion/dbt builds
continuously, which can both add and reclassify rows (hence the mixed sign).
This was not confirmed against a specific Dagster run. **Flagging for the
user**: if Task 9's rollback check needs bit-for-bit reproducibility against the
known-good numbers above rather than against the numbers captured below,
re-verify before relying on this baseline.

The numbers recorded in each section below are the actual captured values (this
document's job is to record current production state, not to force agreement
with an earlier check).

## Rows by source and response_type

Captured 2026-08-28 ~23:13 UTC.

```sql
select a.type as assessment_type, coalesce(f.response_type, '<null>') as response_type, count(*) as n
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
inner join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key
inner join kipptaf_marts.dim_assessments as a on d.assessment_key = a.assessment_key
group by 1, 2 order by 1, 2
```

```text
| assessment_type        | response_type | n       |
| ----------------------- | ------------- | ------- |
| dibels                  | <null>        | 57546   |
| illuminate               | <null>        | 1073419 |
| illuminate               | group         | 2867068 |
| illuminate               | overall       | 1572565 |
| illuminate               | standard      | 8688150 |
| iready                   | <null>        | 240833  |
| star                     | <null>        | 7349    |
| state_fl_eoc             | <null>        | 260     |
| state_fl_fast            | <null>        | 17780   |
| state_fl_science         | <null>        | 703     |
| state_nj_njgpa           | <null>        | 2288    |
| state_nj_njsla           | <null>        | 35096   |
| state_nj_njsla_science   | <null>        | 6313    |
```

Total across all rows: 14,569,370 (matches the FK-health total below).

## Proficiency by source

Captured 2026-08-28 ~23:14 UTC.

```sql
select a.type as assessment_type, count(*) as count_scores,
       countif(f.is_mastery) as sum_proficient,
       round(100 * countif(f.is_mastery) / nullif(count(*), 0), 2) as pct_proficient
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
inner join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key
inner join kipptaf_marts.dim_assessments as a on d.assessment_key = a.assessment_key
group by 1 order by 1
```

```text
| assessment_type        | count_scores | sum_proficient | pct_proficient |
| ----------------------- | ------------ | --------------- | -------------- |
| dibels                  | 57546        | 26128           | 45.40          |
| illuminate               | 14201202     | 6503953         | 45.80          |
| iready                   | 240833       | 61173           | 25.40          |
| star                     | 7349         | 2469            | 33.60           |
| state_fl_eoc             | 260          | 163             | 62.69          |
| state_fl_fast            | 17780        | 4132            | 23.24          |
| state_fl_science         | 703          | 229             | 32.57          |
| state_nj_njgpa           | 2288         | 891             | 38.94          |
| state_nj_njsla           | 35096        | 10154           | 28.93          |
| state_nj_njsla_science   | 6313         | 450             | 7.13           |
```

## Pre-change key sample (rows with NULL response_type)

Captured 2026-08-28 ~23:16 UTC. `assessment_score_key` is a
`dbt_utils.generate_surrogate_key` hash — no PII. Sample of the first 20 keys
(by key value) among `response_type IS NULL` rows:

```sql
select assessment_score_key from kipptaf_marts.fct_assessment_scores_enrollment_scoped
where response_type is null order by assessment_score_key
```

```text
000004ae9e9ce508b248d0a62e799fbf
000031fb2e342e051926b463646938b2
0000335ac491214dcbe5b625000e46fd
00006710f9d5f1cff981d227f2e018ff
0000692b2569365803709e671a3adfad
00006ac5046ad0346f1a5617f7ca291b
00006e583a8c51c33ed4baa240f0ccab
000073b3faa55fc90c98463dd7296fd6
000073bc852f5405da50b5111829f6ca
00007b4117151cd0d950c77e93d5c615
00009bf09dd0e2c95b120566b15c9714
00009d243029f3d35f25b41fb97af165
0000a9aacd622699417a36f7311ef6aa
0000ac88a521247d4a8b0ca60abde5f0
0000aef6ff67013f99b903adf5aa8931
0000b087650b174e1a75bba41f3cbb72
0000bed0ddbdbb3df18e1dbbf4a5cb13
0000d051660c819c5164fbed5e0c642f
0000df190427318d266a12b6cf57ace1
0000ec87e75b05084dad61ce0d67a265
```

(A `--limit 20` was passed to `dbt show`, not an inline `LIMIT` — `dbt show`
appends its own `LIMIT`, and a second inline one is a syntax error.)

## FK health

Captured 2026-08-28 ~23:15 UTC.

```sql
select countif(d.assessment_administration_key is null) as orphans, count(*) as n
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
left join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key
```

```text
| orphans | n        |
| ------- | -------- |
| 0       | 14569370 |
```

Zero orphans — every `fct_assessment_scores_enrollment_scoped` row resolves to a
`dim_assessment_administrations` row.

## Pre-aggregation

Cube's `proficiency_rollup` pre-aggregation
(`src/cube/model/cubes/student_assessments/student_assessment_scores.yml`) is
year-partitioned (`partition_granularity: year`), bounded
`build_range_start: 2015-07-01` to `build_range_end: CURRENT_DATE`, refreshed
daily (`refresh_key: { every: 1 day }`).

Captured via the `JOBS_BY_PROJECT` method in `src/cube/CLAUDE.md`: queried
`` `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT `` for
`user_email = 'cube-cloud@teamster-332318.iam.gserviceaccount.com'` and
`query LIKE '%proficiency_rollup%'`, isolated to the most recent daily build
batch (2026-08-28T00:04:57Z–2026-08-28T00:16:42Z UTC — this was already the
newest batch; nothing ran later that day under the daily refresh cadence).

- **Partition count: 12** — one per academic year, 2015 through 2026 inclusive
  (read off the `student_assessment_scores_proficiency_rollup <YYYYMMDD>_...`
  destination-table names loaded into `prod_pre_aggregations` during the batch:
  `20150101`, `20160101`, `20170101`, `20180101`, `20190101`, `20200101`,
  `20210101`, `20220101`, `20230101`, `20240101`, `20250101`, `20260101`).
  Matches the ~12-partition estimate in the model's config comment.
- **Build bytes**: the batch contains 44 jobs total — 22 `QUERY` jobs writing to
  the `prod_pre_aggregations` dataset (each `total_bytes_processed = 0`; these
  are the partition-load jobs, and several partitions were loaded more than once
  in this batch — e.g. the 2026 and 2018 partitions each appear 2-3 times,
  likely retries) and 22 `QUERY` jobs writing to an anonymous dataset
  (`_52289cbabf87c9bcd5e7924a6ab9fe4386a102a5`) that did the actual computation
  against `kipptaf_marts`.
  - Summed across all 22 compute jobs as they actually ran (including repeats):
    **1,547,289,982 bytes** (~1.44 GiB).
  - Summed across the 12 distinct byte values (one per partition, collapsing
    exact-duplicate repeats): **787,241,167 bytes** (~750.6 MiB) — this is the
    more likely reading of "per-partition build cost," since the duplicate jobs
    reprocessed identical byte counts rather than doing additional distinct
    work.
  - Neither figure was cross-checked against a second, independent method (e.g.
    Cube Cloud's own build-history UI) — recorded as read directly off
    `JOBS_BY_PROJECT`.
