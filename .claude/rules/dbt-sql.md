---
paths:
  - "**/src/dbt/**/*.sql"
---

# dbt SQL conventions

Loads on the first read of a `.sql` file under `src/dbt/`. Applies to every dbt
project in the repo. The section between the snippet markers is the published
standard (`docs/reference/dbt-conventions.md` includes it); cite rules by ID in
reviews. Everything after it is detail and traps for Claude. Architecture rules:
`.claude/rules/dbt-architecture.md`. Project-level rules: `src/dbt/CLAUDE.md`
and `.claude/rules/dbt-models.md`.

<!-- --8<-- [start:sql-style] -->

## SQL style

Our base is dbt Labs'
[How we style our SQL](https://docs.getdbt.com/best-practices/how-we-style/2-how-we-style-our-sql):
lowercase, trailing commas, explicit `inner join` / `left join`, and CTEs over
subqueries. sqlfmt and sqlfluff (`.trunk/config/.sqlfluff`) enforce the
formatting. The rules below are where we add to or differ from that guide.

### Where we differ from dbt Labs

| Rule                             | dbt Labs                | Us                   | Why                                                      |
| -------------------------------- | ----------------------- | -------------------- | -------------------------------------------------------- |
| Import CTEs                      | Recommended             | Banned (S4)          | A CTE with no logic; `ref()` in `from` reads the same    |
| `qualify`                        | Allowed                 | Banned (S1)          | Not ANSI SQL; a ranked column plus `where` does the same |
| `group by 1, 2` / `group by all` | Prefers `group by 1, 2` | Banned (S1, S2)      | Both break silently when the select list changes         |
| Table aliases                    | Full names, no initials | Short initials (S16) | The repo norm; unique in the query                       |

### Rules

Common remedy for S3, S8, S9, and S10: derive the expression as a named column
in an upstream CTE, then reference the plain column.

#### S1. ANSI SQL or a dbt macro first

Use BigQuery-only syntax only when it does something standard SQL cannot.
`qualify`, `group by all`, and `union all corresponding` never pass that test.

- Why: standard SQL reads the same to everyone and ports between engines.
- Good: `row_number() over (...) as rn` in 1 CTE, `where rn = 1` in the next.
- Bad: `qualify row_number() over (...) = 1`.
- Enforced by: `sql-banned-syntax`.

#### S2. Name every `group by` column

- Why: positional grouping breaks silently when the select list is reordered.
- Good: `group by student_number, academic_year`.
- Bad: `group by 1, 2`.
- Enforced by: review.

#### S3. No subqueries against tables or CTEs

Write a CTE and join it. The 1 exception is a scalar aggregate over `unnest` of
an array, which is row-local.

- Why: a CTE has a name and can be read and tested on its own.
- Good: `(select min(x) from unnest([d1, d2, d3]) as x) as earliest_date`.
- Bad: `where student_number in (select student_number from enrolled)`.
- Enforced by: review.

#### S4. No pass-through import CTEs

Reference `ref()` and `source()` directly in `from` and `join`. Every CTE does
real work.

- Why: a CTE that only renames a ref adds a hop and no logic.
- Good: `from {{ ref("stg_powerschool__students") }} as s`.
- Bad: `students as (select * from {{ ref("stg_powerschool__students") }})`.
- Enforced by: review.

#### S5. No `order by` in models

- Why: ordering belongs to the tool that displays the data.
- Good: no `order by` in the final select.
- Bad: `order by student_number` at the end of a model.
- Enforced by: review.

#### S6. Order the select list by complexity

Our house order, with no interleaving:

1. Plain columns, grouped by source table in join order, with a blank line
   between tables
2. Constants and literals
3. Simple functions (`coalesce(...)`, simple `if(...)`)
4. Nested functions
5. Logicals (`if(condition, true, false)`)
6. Case statements
7. Window functions (`row_number() over (...)`)

When a select reads from 1 table or CTE, do not prefix columns with an alias.

- Why: a reader finds the plain columns first and the logic last.
- Good: plain columns, then `coalesce(...)`, then `case ... end`.
- Bad: a `case` between 2 plain columns.
- Enforced by: review.

#### S7. sqlfluff ST06 select order

sqlfluff's own rule, separate from S6: wildcards, then plain columns, then
calculations. It treats `cast()` as a plain column.

- Why: lint consistency.
- Good: `cast(x as int64) as x` before `date(y) as y_date`.
- Bad: `date(y) as y_date` before `cast(x as int64) as x`.
- Enforced by: sqlfluff ST06.

#### S8. At most 1 level of function nesting

Aggregates passed as direct arguments do not count.

- Why: nested calls hide intermediate values a reader needs to check.
- Good: `if(coalesce(x, y) > 0, 'a', 'b')`;
  `round(safe_divide(sum(a), sum(b)), 2)`.
- Bad: `if(coalesce(cast(x as int64), 0) > 0, 'a', 'b')`.
- Enforced by: review.

#### S9. Cast early, once, with an alias

Cast in staging or where the raw value first appears, as a named column. Never
nest `cast()` inside another function.

- Why: 1 typed column downstream; an unaliased `cast()` is named `f0_` by
  BigQuery.
- Good: `cast(student_id as string) as student_id` in staging.
- Bad: `date(cast(entry_ts as timestamp))` in a mart.
- Enforced by: review.

#### S10. No calculations on table columns in `where` or 1-sided in `on`

Precompute them as named columns upstream. Literals, `{{ var(...) }}`, and
`current_date(...)` on the other side are fine; so are expressions that combine
both join sides.

- Why: the filter or join reads as plain columns, and the derived value can be
  tested.
- Good: `where is_enrolled`.
- Bad: `where date_diff(exit_date, entry_date, day) > 0`.
- Enforced by: review.

#### S11. Row filters on the preserved table go in `where`

For a `left join`, a filter in `on` keeps non-matching rows. Exception: a
`full join` condition on 1 side stays in `on`.

- Why: `on` decides matches; `where` decides rows.
- Good: `left join t on a.id = t.id where a.is_active`.
- Bad: `left join t on a.id = t.id and a.is_active`.
- Enforced by: review.

#### S12. `distinct` only for grain projection

Use `distinct` for a grouping with no aggregate, or when every column is fixed
by the partition key; annotate it `grain projection, not dup-masking`. Never use
it to hide duplicates.

- Why: a masking `distinct` hides which row was meant.
- Good: `select distinct student_number, academic_year` with the annotation.
- Bad: `select distinct *` after a join that fans out.
- Enforced by: review.

#### S13. Half-open intervals for date ranges that touch

When ranges can share a boundary date, use `>=` start and `<` end, not
`between`.

- Why: `between` matches both ranges on the shared date and fans out.
- Good: `enr.entrydate <= cc.dateenrolled and enr.exitdate > cc.dateenrolled`.
- Bad: `cc.dateenrolled between enr.entrydate and enr.exitdate` across
  enrollment stints.
- Enforced by: review.

#### S14. Booleans are `is_` / `has_` columns

Convert to `Y`/`N` text only inside an `rpt_` whose tool needs it. A fact's
countable flags may be `int64` 0/1 instead (mart rubric R3).

- Why: a boolean filters and aggregates directly.
- Good: `is_enrolled` (`bool`).
- Bad: `enrolled_flag` with values `'Y'` / `'N'` in an intermediate.
- Enforced by: review.

#### S15. `if()` for 1 condition, `case` for 2 or more

- Why: each form reads best at its own size.
- Good: `if(score >= 70, 'pass', 'fail')`.
- Bad: nested `if(a, 'x', if(b, 'y', 'z'))`.
- Enforced by: review.

#### S16. Short table aliases, unique in the query

Derive them from the model name.

- Why: short aliases keep joins readable; the repo already uses them.
- Good: `int_extracts__student_enrollments as e`.
- Bad: `as t1`, or 2 tables both aliased `s`.
- Enforced by: review.

#### S17. `union all` branches list the same columns in the same order

Pad a missing column with `cast(null as <type>) as <col>`.

- Why: BigQuery matches branches by position; 2 same-typed columns can swap
  silently.
- Good: each branch selects `student_number, academic_year, score`.
- Bad: `select * from a union all select * from b`.
- Enforced by: review.

#### S18. Comments say only what the line cannot show

Rationale and background go in the model's YAML `description:`.

- Why: SQL comments drift; YAML descriptions are published with the model.
- Good: `-- source resends rows on retry`.
- Bad: a paragraph explaining what the model is for.
- Enforced by: review.

### Review rubric

Reviewers, human or Claude, check these and cite the rule ID:

1. Grain has a uniqueness test, and 1 model owns it (A4).
2. Dedup sits in the right layer; `distinct` is not masking duplicates (A5,
   S12).
3. The model sits in the right layer and is the right kind (A1, A3).
4. An `rpt_` reads a mart when 1 exists (A2).
5. Join types are right; filters sit in `on` or `where` correctly (S10, S11).
6. Date-range joins are half-open where ranges touch (S13).
7. Nested logic is split into named columns past 1 level (S8, S9).
8. Comments say only what the line cannot show (S18).

<!-- --8<-- [end:sql-style] -->

## Rule details and traps

Claude-only. Bullets expand the rules above; the rule ID leads where 1 applies.

Apply the S rules only to lines you add or change. An old violation elsewhere in
the file is not yours to fix, and never propose a sweep of untouched models,
macros, or tests.

The `dbt:using-dbt-for-analytics-engineering` skill's process guidance (plan
backwards, validate results) applies here, but where it conflicts, this file
wins: its test-tiering advice ("avoid liberal `not_null` /
`expression_is_true`") must not remove this repo's intentional
`config.where`-scoped warn tests, its example SQL is non-BigQuery dialect, and
validation/profiling goes through BigQuery MCP, not `dbt show`.

### ST06 traps (S7)

- sqlfluff ST06 buckets `cast()` as a simple target, not a calculation. A
  `cast(...) as x` placed after `date(...)` / `regexp_extract(...)` in the same
  select list fails ST06. Put every `cast()` after the plain column refs and
  before any other function call. S6 still applies to the rest of the list.
- Deleting `{#- ... #}` blocks can newly expose ST06 on adjacent code that main
  passes — sqlfluff skips rules near templated slices. If fixing ST06 would
  reorder a contract/sheet-fixed column list, suppress with the repo-standard
  `trunk-ignore(sqlfluff/ST06)` instead.

### Structure details

- S1: `select * except` is the kind of BigQuery-only form that passes, because
  standard SQL has no equivalent.
- S18: before writing or editing any inline SQL comment, ask whether it would
  survive as a properties.yml `description:` instead (see _YAML conventions_ in
  `.claude/rules/dbt-yaml.md`). The file being open is not evidence it's the
  right place, and the repo's existing multi-paragraph SQL comments are not a
  precedent to extend. Carve-out: TODOs, tracking-issue refs, and migration
  plumbing stay inline at the derivation site — a defect belongs in the code,
  not the metadata.
- S9: the matching alias on a function-wrapped expression
  (`cast(col as type) as col`) is NOT an AL09 self-alias; it's the repo norm.
  Unaliased, a contracted / explicitly-projected `select` gets `f0_` and fails.
- S3: the scalar aggregate over `unnest` is the ONLY blessed `unnest` subquery
  form. An `order by ... limit 1` pick over `unnest` is NOT allowed (S5); for a
  priority pick over a fixed candidate set, use
  `coalesce(if(cond, a, null), ..., a, ...)`, which returns the first non-null
  in priority order with no subquery.
- S3: least/earliest of N nullable columns is
  `(select min(x) from unnest([c1, c2, ...]) as x)` — aggregate `min` ignores
  NULLs, unlike `least()` (which returns NULL if any arg is NULL). Avoids the
  nested `coalesce(..., sentinel)` + outer-guard pyramid. sqlfluff CV03 wants a
  trailing comma on the inner `select min(x),`; the `unnest([...])` array
  literal must NOT have one (BigQuery rejects a trailing comma in an array).
- S5: includes `order by ... limit 1` as a single-row pick inside a scalar
  subquery (express a pick with `coalesce`/`if` or a ranked column filtered by
  `where`). Exempt: macro-generated ordering (`dbt_utils.deduplicate` emits
  `array_agg(... order by ... limit 1)`) and `array(select ... order by ...)`
  element ordering.
- No lateral column aliases. BigQuery rejects a `select`-list alias referenced
  by another item in the same list —
  `select 1 as a, case when a = 1 then 'x' end as b` fails
  `Unrecognized name: a`. It works in Snowflake/DuckDB, so a reviewer may
  propose it to de-duplicate two `case`s that share predicates; hoist to a CTE
  or keep the duplication.
- S12: name the partition key on the annotation when the `select` list does not
  make it obvious. Never `distinct` when a projected column varies within the
  partition (`min()`, `first_value()`) — use `dbt_utils.deduplicate()` (see _Row
  picking, dedup & surrogate keys_) with a `-- TODO:` naming the upstream fix.
  When the upstream already numbers rows at the grain you want (`rn_year` on the
  enrollment models; check the model's `rn_*` columns first), filter on that
  column instead of `distinct`, even if you select only key columns. Once a
  non-key column is added, a `distinct` returns one row per stint again, and a
  later dedup on the old key then picks among them unpredictably.
- S10: expressions that inherently combine columns from both join sides
  (`st_distance(a.geo, b.geo)`, `st_dwithin(...)`) cannot be hoisted and are
  allowed. Column-to-column inequality comparisons (half-open date-range joins)
  are comparisons, not calculations.
- S4: exception — the same-name whole-row-STRUCT collision (see _BigQuery syntax
  traps_) _requires_ reading through a `source` CTE.
- Pre-compute `lag()` / `format()` inputs in the source CTE so the comparison
  CTE compares plain columns. Avoids duplicating the expression inside
  `lag(expr)` and the bare-column reference.
- Soft-delete filters: apply in the staging model, not in downstream `on`
  clauses. Deleted rows should never reach intermediate or mart models. Omit
  columns whose value is predetermined by the `where` filter (e.g., `deleted_at`
  after `where deleted_at is null`) — they add no signal.
- SFTP `source_file_name`: drop in the staging model with
  `select * except (source_file_name)` — the SFTP IO adds it to every row
  (`core/utils/functions.py`); a contracted `stg_*` that doesn't except it fails
  the contract on the next re-pull after the ingestion change.
- Google Sheets external-table case: `select *,` in a staging model inherits the
  sheet header case (often PascalCase). Contract-enforced YAML column names must
  match that case, or use explicit `<raw> as <renamed>` aliasing in the staging
  SQL. Don't rename columns in `sources-external.yml` just to normalize case —
  that rebuilds the external table and forces sheet-header coordination.
- Timezone-aware today:

  ```sql
  current_date('{{ var("local_timezone") }}')
  ```

## `select *` and UNION branches

- No `select *` in the final `select` of `rpt_`/mart models (A9). Get the
  authoritative column list via `INFORMATION_SCHEMA.COLUMNS`:

  ```sql
  select column_name
  from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
  where table_name = '<model_name>'
  order by ordinal_position
  ```

- S17: `select *` inside UNION ALL CTEs also trips CV03 — sqlfluff requires a
  trailing comma after the last column, but `select *` has nothing to trail. In
  a VIEW model, enumerating is also what lets an upstream column add reach the
  view at all: BigQuery fixes a view's column list when the view is created, and
  Dagster rebuilds a view only on `code_version_changed`, which hashes the
  model's raw SQL. A `select *` view never picks up a column an upstream adds,
  because its own raw SQL never changes. Enumerating makes the column add an
  edit to the view's own SQL, so it recompiles on deploy.
- A standalone `select *` takes a trailing comma (`select *,`) to satisfy
  sqlfluff CV03 (e.g. `stg_overgrad__schools.sql`; a `source` CTE) — distinct
  from the UNION-ALL case above, which must enumerate columns.
- `select * replace (...)` only for simple conversions. A column that is
  excepted from `*` and re-added under its own name as a plain `cast`,
  `safe_cast`, or `parse_date` goes in `replace`. Anything that branches or
  merges — `coalesce`, `if`, `case` — stays as `except` plus an explicit re-add,
  so the logic reads in the select list rather than inside the star. Renamed or
  merged-away columns stay in `except`; both clauses can sit on one `*`.
- DATE literal across UNION ALL branches needs explicit cast: BQ coerces
  `'9999-12-31'` to DATE inside `coalesce(date_col, ...)` but NOT across UNION
  ALL branches when one side is CTE-typed STRING. Use
  `cast('9999-12-31' as date)`. Avoid the `date '9999-12-31'` typed-literal
  form.

## Date-range joins (S13)

Consecutive student enrollment stints share a boundary date (a stint's
`exitdate` equals the next stint's `entrydate`), so `between` matches both and
fans out:

```sql
-- wrong: matches both stints on the shared boundary
and cc.dateenrolled between enr.entrydate and enr.exitdate

-- right: half-open interval
and enr.entrydate <= cc.dateenrolled
and enr.exitdate > cc.dateenrolled
```

`between` is fine — and is the repo norm — for joins to non-overlapping,
non-abutting windows (calendar weeks, reporting terms, topline period rows),
where a point date matches at most one interval.

## Row picking, dedup & surrogate keys

### Nullable surrogate keys

`dbt_utils.generate_surrogate_key()` hashes NULL inputs into a deterministic
placeholder string — it never returns NULL. When a surrogate key column can be
null (e.g., from a LEFT JOIN), wrap the call:

```sql
if(
    source_column is not null,
    {{ dbt_utils.generate_surrogate_key(["source_column"]) }},
    cast(null as string)
) as fk_column,
```

Without this, relationship tests check the placeholder hash against the parent
dimension and fail.

**Never add a `not_null` test to `generate_surrogate_key` output** — it never
returns NULL, so the test cannot fail. This holds for FK columns as much as PKs.

**`dbt_utils.generate_surrogate_key` coerces nulls internally** —
`cast(null as <type>)` and bare `null` hash identically. Don't add the cast.

### Nullable PK inputs need a fallback, not a null-wrap

For a primary key (not an FK), wrapping `generate_surrogate_key` in
`if(col is not null, ..., cast(null as string))` makes the PK nullable and fails
`not_null`. Use a fallback discriminator inside the hash inputs:
`coalesce(cast(primary_id as string), secondary_id)`. The secondary id must be
unique-per-row within the rows the primary would have disambiguated — otherwise
rows with NULL primary collide on the placeholder hash and fail `unique`.

### dbt_utils.deduplicate `order_by` on BigQuery

The macro compiles to `array_agg(original order by <expr> limit 1)`. BigQuery
rejects `asc nulls last` and `desc nulls first` inside aggregate `array_agg`.
Use `desc` (default NULLS LAST) or `(col is null) asc` instead of explicit
`nulls last` with ascending sort.

**`partition_by` must match the downstream join key**, not the source PK.
Partitioning by the source's natural key leaves multiple rows that share the
intended join column, which then fan out at the join site. Use
`(col = 'sentinel') asc` in `order_by` to demote a specific value when rows tie
on the chosen partition key.

**Picked-row attrs include NULL — don't `coalesce` to a fallback row.** When
`dbt_utils.deduplicate(partition_by=X, order_by=Y)` replicates
`first_value(...) over (partition by X order by Y)` canonical-pick semantics,
the picked row's value is authoritative including NULL.
`coalesce(picked.attr, fallback.attr)` silently substitutes a different row's
value when the canonical pick is NULL — breaks downstream GROUP BY / uniqueness
invariants. Use
`if(<row-belongs-to-picked-partition>, picked.attr, fallback.attr)` to branch on
row-membership, not on value-nullness.

**A CTE referenced only via `dbt_utils.deduplicate(relation="<cte>")` fails
sqlfluff ST03.** Add
`# trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`
above the CTE.

### dbt_utils.deduplicate cost: ranked column above ~1M rows

The macro compiles on BigQuery to
`array_agg(original order by <expr> limit 1)[offset(0)]` grouped by the
partition key. That packs the whole row into a struct, inflates the input
shuffle, and pushes the aggregate past BigQuery's single-round-shuffle threshold
— so the plan gains `Repartition` stages that a window function never emits.

Do not re-derive this: the ranked form was faster at every size measured, and
the ~1M-row threshold below is interpolated, not a measured inflection point
(evidence: #5252). Below it the saving doesn't repay the extra CTE.

The default stays `dbt_utils.deduplicate()` — it is one call, and `qualify` is
banned (S1), so the window form always costs an extra CTE plus an `rn` column.
Switch to the ranked-column form only when BOTH hold: the dedup input exceeds
about 1M rows, AND the model costs at least 1 slot hour in the 7-day prod
ranking. A caller that doesn't clear both bars stays on
`dbt_utils.deduplicate()`; this is not license for a repo-wide sweep.

```sql
with
    <input>_ranked as (
        select
            <columns>,

            row_number() over (
                partition by <key> order by <expr> desc
            ) as rn,
        from {{ source(...) }}
    )

select <columns>,
from <input>_ranked
where rn = 1
```

When `<input>` is a plain `select` (not a `UNION ALL`), inline the window
directly into that CTE instead of adding a separate wrapper — no `_ranked` CTE
needed. When `<input>` IS a `UNION ALL`, the window must sit in a separate CTE
(named `<input>_ranked`) that reads the whole union — ranking inside each union
branch separately ranks per-branch and breaks the tie-break.

Three traps when converting:

- A filter that ran AFTER the macro (a soft-delete predicate, typically) shares
  the `WHERE` with `rn = 1`. It must not sit in the CTE that computes `rn` — the
  window is evaluated before either predicate applies, so moving the filter up
  changes which row wins.
- Do not `select * except (rn)` to drop the helper column. Enumerate the output
  columns instead.
- Don't carry the `(col is null) asc` NULL-ordering workaround (see
  _dbt_utils.deduplicate `order_by` on BigQuery_ above) over into the ranked
  form — that workaround exists because BigQuery rejects `nulls last` inside
  `array_agg`, a macro-only constraint. A window function's `order by` takes
  explicit `nulls last` directly.

### Don't inline CASE expressions in generate_surrogate_key

`dbt_utils.generate_surrogate_key(["case <col> when ... end"])` compiles via
Jinja's implicit-string-concat across adjacent list elements — unreviewable, and
a comma inserted between fragments silently changes the SQL. Derive the computed
value as a named column in an upstream CTE, then hash that column.

### Namespace UNION-ed `generate_surrogate_key` branches

When two `generate_surrogate_key()` calls feed `UNION ALL` into one key column,
prepend a branch-discriminator literal (`"'left'"` / `"'right'"`) as the first
input. `generate_surrogate_key` stringifies inputs, so `'1'` (string) and `1`
(int) collide when remaining inputs align.

### Canonical attributes from a partition

Use `first_value(... order by <pk>)` for every attribute, not separate `min()`
calls — independent mins on different columns can pick from different rows in
the same partition.

## BigQuery syntax traps

- **`WITH RECURSIVE` needs `contract: enforced: false`.** BigQuery allows
  `WITH RECURSIVE` only at the top level of a statement, but dbt's contract
  validation (and the table CTAS) wrap the model SQL in a subquery — so a
  recursive model fails with "WITH RECURSIVE is only allowed at the top level".
  Set `contract: enforced: false` on the model and keep `relationships`/
  uniqueness data tests for coverage. A bounded Jinja unroll is the alternative
  but hits "query is too complex" when it re-expands view upstreams once per
  level.
- **A projected column whose name equals its source table binds to the whole-row
  STRUCT, not the column**: a bare `address` ref in
  `from {{ source("focus", "address") }}` resolves to the table range variable
  (dbt's component-backtick `` `proj`.`ds`.`address` `` form), so the model
  silently outputs one struct column and the contract fails listing every field
  as `address.<col>`. Read through a `source` CTE
  (`with source as (select *, from {{ source(...) }})`). A single-backtick MCP
  repro `` `proj.ds.table` `` does NOT reproduce it — use component backticks.
- **BigQuery rejects `\_` in a string literal** (`Illegal escape sequence`).
  Escaping an underscore in a `LIKE` needs `'%\\_focus%'`.
- **BigQuery-reserved CTE names**: `groups` is reserved (window-frame syntax
  `OVER (... GROUPS BETWEEN ...)`). A CTE named `groups` fails parsing with
  "Expected keyword SELECT but got keyword GROUPS". Use `reporting_groups` or
  similar. `grouping` is reserved too (`GROUPING SETS`): an alias named
  `grouping` needs backticks.
- **BigQuery `PIVOT` operator**: pivots ONE value column per aggregate. For a
  mixed-type key-value array, use a multi-aggregate pivot —
  `pivot(max(v_str) as s, max(v_bool) as b, any_value(v_arr) as a for field_name in ('x', ...))`
  — then project the typed column per field (`s_x as x` / `b_x as x`). Output
  columns are `{agg_alias}_{value}`; a SINGLE-aggregate pivot names them by the
  bare value (`'x'` → column `x`). `max()` can't aggregate ARRAY — use
  `any_value()` for array fields. A reserved-word aggregate alias (e.g. `name`)
  must be backticked (sqlfluff RF04); the backtick doesn't change the produced
  column name (`name_<value>`).
- **BigQuery `UNPIVOT` excludes null rows** — an entity whose unpivoted columns
  are all null drops out of the result. Harmless for a pure decode companion (a
  left join from staging yields null labels anyway), but when the model also
  LEFT JOINs a separately-computed field (e.g. a `multiple`/array decode), drive
  the final `SELECT` from the full entity list or that field is lost for
  all-null-unpivoted entities.

## sqlfluff rule traps

All SQL follows `.trunk/config/.sqlfluff` (BigQuery dialect), enforced by CI —
**do not flag code that already follows it.** ST06 traps are under _ST06 traps
(S7)_; CV03 is under _`select *` and UNION branches_.

- **sqlfluff ST09 (join order)**: ON-clause predicates list the
  earlier-referenced table on the left, including predicates inside a current
  join that reference a prior-joined table. After
  `from A ... join B ... join C on X`, predicates referencing both `B` and `C`
  write `B.x = C.y`, not `C.y = B.x`.
- **AL09 on struct subfields**: `value.string_value as string_value` trips AL09
  (alias equals the leaf name). Rename to a distinct alias (`as value_string`)
  rather than dropping it when a downstream PIVOT/ref needs the column named.
- **sqlfmt rejoins statements once a mid-statement comment is gone** (`from` /
  `select *,` collapse to one line) — let the pre-commit fmt hook apply it.

## Verifying a comment-only SQL change

Strip `--`, `/* */`, and `{# #}` comments from the old and new blobs, collapse
whitespace, and compare — token identity proves no logic change, and it works
where a dev build cannot (stale personal `zz_` source copies, which
`--favor-state` does not defer). Compiled-SQL identity via `dbt compile` is the
equivalent fallback per model.
