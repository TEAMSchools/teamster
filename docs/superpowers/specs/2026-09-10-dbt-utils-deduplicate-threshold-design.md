# `dbt_utils.deduplicate` cost threshold

Design for [#5252](https://github.com/TEAMSchools/teamster/issues/5252). Follows
#5216 / #5249. Parent: #5212.

## Problem

`dbt_utils.deduplicate` compiles on BigQuery to
`array_agg(original order by <expr> limit 1)[offset(0)]` grouped by the
partition key. That packs the whole row into a struct and pushes it through the
shuffle.

Two prod rewrites showed large wins: `stg_deanslist__behavior` went from about
461 to about 81 slot-minutes per run (#5249, merged), and
`int_powerschool__category_grades` went from 20.3 to 2.8 slot-minutes (#5213).
The tempting conclusion is to sweep every caller. #5252 exists to establish
where the tax is actually worth paying down, and to stop there.

## Measurement

### Method

Four prod tables spanning row count and row width independently. For each, two
arms against the same table:

- **Arm A**, the macro's compiled form:
  `select unique.* from (select array_agg(original order by <ob> limit 1)[offset(0)] unique from <rel> original group by <pb>)`
- **Arm B**, the ranked-column form: `row_number()` in one CTE, `where rn = 1`
  in the next.

Both arms wrapped in `sum(length(to_json_string(t)))` to force full-row
materialization, so neither arm could win by column pruning. Slot time and
per-stage shuffle bytes read from
`` `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT ``. No cache hits. Every pair
returned byte-identical output.

### Results

| Table                               |       Rows | Bytes/row | Cols | Macro slot-min | Ranked slot-min | Ratio | Macro shuffle | Ranked shuffle |
| ----------------------------------- | ---------: | --------: | ---: | -------------: | --------------: | ----: | ------------: | -------------: |
| `stg_deanslist__behavior`           | 44,473,677 |       241 |   32 |         117.11 |           17.75 |  6.6x |     66.07 GiB |      12.20 GiB |
| `students_assessments` (illuminate) |  4,155,044 |        56 |    7 |           3.48 |            0.76 |  4.6x |      1.63 GiB |       0.23 GiB |
| `stg_schoolmint_grow__observations` |    125,167 |      3629 |   71 |           1.27 |            0.58 |  2.2x |      1.01 GiB |       0.60 GiB |
| `stg_finalsite__status_report`      |     18,167 |       195 |   65 |           0.11 |            0.05 |  2.5x |      0.02 GiB |       0.00 GiB |

### Conclusion

**Row count drives the penalty. Row width does not.** The widest table
(schoolmint, 3629 bytes/row, 71 columns) shows the smallest penalty. The
narrowest (illuminate, 56 bytes/row, 7 columns) shows a larger one. The issue's
stated suspicion — that width may matter more than row count — is refuted, and
the rule text says so explicitly so nobody re-derives it.

**Mechanism**, from `unnest(job_stages)`: the macro form makes BigQuery add
`Repartition` stages the window form never emits. Deanslist arm A ran 8
repartition stages moving about 22 GiB on top of a 43.05 GiB Input shuffle. Arm
B was `Input -> Sort+ -> Output`, 12.20 GiB total. The whole-row struct both
inflates the Input shuffle and pushes the aggregate past BigQuery's
single-round-shuffle threshold, which is a function of group count, not row
width.

**The ranked form never lost**, at any size tested.

### Caveat: absolute savings are upper bounds

The `to_json_string` wrapper inflates both arms and does not fully cancel. On
illuminate the implied per-run saving (2.72 slot-minutes) exceeds that model's
entire per-run cost (about 1.21 slot-minutes), which cannot be right: in arm A
the projection runs on struct-unpacked rows, in arm B on plain rows, so the two
projections are not equal work.

Trust the ratios and the shuffle bytes. Shuffle is measured before the final
projection, so it is wrapper-independent. The ratios are corroborated by real
prod rewrites: 5.7x on deanslist (#5249) against 6.6x measured here on the same
table, and 7.2x on #5213.

Do not quote the per-run slot-minute deltas as estimates.

## Corrections to the issue premise

Both were found while re-running the diagnostic and both change the rewrite
list.

### 8 of the callers are disabled code

`src/dbt/powerschool/models/sis/staging/odbc/` is archived under #4442 and set
`+enabled: false` in `dbt_project.yml`. The live `dlt/` variants of those models
do not call the macro. Eight callers sit in that directory, including
`stg_powerschool__pgfinalgrades` — the issue's #2 rewrite candidate at 12.9 slot
hours.

The cost ranking extracts `node_id` from the query comment, which carries the
model name and cannot tell the three ingestion variants apart. So those 12.9
slot hours belong to the live `dlt/` model, which has no dedup in it. Across 6
nodes, 14.3 slot hours are misattributed this way.

The `dlt/` copies of `u_clg_et_stu` and `u_clg_et_stu_alt` are genuine callers,
at 0.04 and 0.03 slot hours.

### The caller-list grep counts comments

`grep -rl "dbt_utils.deduplicate"` matches any file mentioning the macro,
including a model rewritten away from it that kept an inline comment saying so.
#5249 created exactly that case. Count invocations instead:

```sh
grep -rl -E "^[[:space:]]*(\{\{[[:space:]]*)?dbt_utils\.deduplicate\(" \
  src/dbt/*/models --include='*.sql'
```

Current main: 116 real callers, of which 108 are live.

## Design

### The rule

`dbt_utils.deduplicate()` stays the default. `QUALIFY` is banned in this repo,
so the window form always costs an extra CTE plus an `rn` column that cannot be
dropped with `except` — real readability churn across 108 models that the
measurement does not capture. Keeping the macro as the default is what stops
this finding from becoming a repo-wide sweep.

`.claude/rules/dbt-sql.md` gains, under _Row picking, dedup & surrogate keys_:

- What the macro compiles to and why that costs (struct in the shuffle, extra
  repartition hops).
- The threshold: above about 1M rows in the dedup input, use the ranked-column
  form instead.
- The evidence table above, condensed.
- The explicit statement that row count drives it and width does not.
- The replacement shape and both traps, so a reader who crosses the threshold
  has what they need without leaving the file.

### Rewrite gate

A caller is rewritten only if **both** hold:

1. The dedup input exceeds about 1M rows.
2. The model costs at least 1 slot hour in the 7-day prod ranking.

Size the **actual dedup relation**, not the model's output. Most candidates
dedup a mid-model CTE, and a downstream join fan-out means output rows are not a
lower bound on dedup input.

### Candidates

| Node                                                    | 7-day slot hours | Disposition                                   |
| ------------------------------------------------------- | ---------------: | --------------------------------------------- |
| `int_assessments__resolved_section_enrollments`         |            16.74 | Size the dedup CTE; rewrite if it clears 1M   |
| `fct_assessment_scores_enrollment_scoped`               |            12.91 | Size the dedup CTE; rewrite if it clears 1M   |
| `int_assessments__scaffold`                             |             7.08 | Size the dedup CTE; rewrite if it clears 1M   |
| `stg_illuminate__dna_assessments__students_assessments` |             1.03 | 4.16M rows, measured. Passes both conditions  |
| `stg_schoolmint_grow__observations`                     |             9.97 | 125k rows, measured. **Fails the gate; skip** |
| Everything else                                         |                — | No                                            |

`stg_deanslist__behavior` is excluded: #5249 already rewrote it and merged.

### Verification per rewrite

Unchanged from the issue and not negotiable. These are contract-enforced models
and dbt Cloud CI builds kipptaf only, so each rewrite gets a value-level proof:
run old and new compiled SQL against the same prod snapshot in one query,
full-outer-join on the model's key, and compare `to_json_string` across every
output column in contract order. Expect 0 only-in-old, 0 only-in-new, 0
differing.

Two traps carried forward from #5216:

1. A filter that ran after the macro (a soft-delete predicate, typically) cannot
   move ahead of the window. It can share the `WHERE` with `rn = 1`, because the
   window is evaluated in the previous CTE before either predicate applies. It
   must not sit in the CTE that computes `rn`.
2. Do not use `select * except (rn)` to drop the helper column. A downstream CTE
   that enumerates its columns does not need it.

## Out of scope

The issue's original done-when — no caller above 10 slot hours — is dropped. The
macro swap cannot deliver it: on schoolmint the swap is worth about 1 of that
model's 9.97 slot hours, and the same is likely true of the two nodes above 10.
Their remaining cost is not the macro.

That leftover cost goes to a new issue under the #5212 parent, covering whatever
keeps `int_assessments__resolved_section_enrollments` and
`fct_assessment_scores_enrollment_scoped` above 10 slot hours after the swap.

## Done when

1. `.claude/rules/dbt-sql.md` carries the threshold, the evidence, and the
   row-count-not-width conclusion.
2. Every candidate that clears the gate is rewritten, each with its value-level
   proof recorded.
3. Every candidate that fails the gate is recorded as measured-and-skipped, so
   the next reader does not re-measure it.
4. The issue body is corrected for the disabled `odbc/` callers and the
   comment-matching grep.
5. The follow-up issue for the non-macro cost is open.
