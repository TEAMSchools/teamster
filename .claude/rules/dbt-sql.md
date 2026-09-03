---
paths:
  - "**/src/dbt/**/*.sql"
---

# dbt SQL conventions

Loads on the first read of a `.sql` file under `src/dbt/`. Applies to every dbt
project in the repo. Project-level and cross-cutting rules: `src/dbt/CLAUDE.md`
and `.claude/rules/dbt-models.md`.

## `WITH RECURSIVE` needs `contract: enforced: false`

BigQuery allows `WITH RECURSIVE` only at the top level of a statement, but dbt's
contract validation (and the table CTAS) wrap the model SQL in a subquery — so a
recursive model fails with "WITH RECURSIVE is only allowed at the top level".
Set `contract: enforced: false` on the model and keep `relationships`/uniqueness
data tests for coverage. A bounded Jinja unroll is the alternative but hits
"query is too complex" when it re-expands view upstreams once per level.

## Date-range joins

Use half-open intervals when joining a point date to intervals that can **abut
or overlap**. Consecutive student enrollment stints share a boundary date (a
stint's `exitdate` equals the next stint's `entrydate`), so `BETWEEN` matches
both and fans out:

```sql
-- wrong: matches both stints on the shared boundary
and cc.dateenrolled between enr.entrydate and enr.exitdate

-- right: half-open interval
and enr.entrydate <= cc.dateenrolled
and enr.exitdate > cc.dateenrolled
```

`BETWEEN` is fine — and is the repo norm — for joins to **non-overlapping,
non-abutting** windows (calendar weeks, reporting terms, topline period rows),
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

### sqlfluff ST03 on dbt_utils.deduplicate input CTEs

A CTE referenced only via `dbt_utils.deduplicate(relation="<cte>")` fails
sqlfluff ST03. Add
`# trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`
above the CTE.

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

## SQL conventions

`sqlfmt` / `sqlfluff` enforce formatting (see _SQL formatting_ below); the rules
here enforce reviewability. Common remedy for the restructure prohibitions:
derive the expression as a **named column in an upstream CTE**, then reference
the plain column.

The `dbt:using-dbt-for-analytics-engineering` skill's process guidance (plan
backwards, validate results) applies here, but where it conflicts, this file
wins: its test-tiering advice ("avoid liberal `not_null` /
`expression_is_true`") must not remove this repo's intentional
`config.where`-scoped warn tests, its example SQL is non-BigQuery dialect, and
validation/profiling goes through BigQuery MCP, not `dbt show`.

- **Before writing or editing any inline SQL comment, stop and ask: would this
  survive as a properties.yml `description:` instead?** A comment explaining
  rationale, background, or what/why a model computes belongs in the properties
  file (see _YAML conventions_ in `.claude/rules/dbt-yaml.md`) — not the SQL,
  even mid-edit on a `.sql` file where the note feels like natural momentum. The
  file being open is not evidence it's the right place. Keep inline SQL comments
  to what a reader of that exact line cannot see — a non-obvious fallback, why a
  filter exists. Carve-out: TODOs, tracking-issue refs, and migration plumbing
  stay inline at the derivation site — a defect belongs in the code, not the
  metadata.
- **Max 1 level of function nesting.** `if(coalesce(x, y) > 0, 'a', 'b')` is at
  the limit; anything deeper gets split into a CTE. Aggregates as direct
  function arguments don't count toward depth —
  `round(safe_divide(sum(a), sum(b)), 2)` is fine.
- **Cast early, once.** `cast()` belongs in staging, or at the earliest point
  where the raw value first appears, as a named column. Downstream expressions
  operate on already-typed columns — never nest `cast()` inside another
  function.
- **`cast(col as type)` needs an explicit alias** — unaliased, BigQuery names
  the column `f0_`, not `col`, so a contracted / explicitly-projected `select`
  gets the wrong column name and fails. Write `cast(col as type) as col`; the
  matching alias on a function-wrapped expression is NOT an AL09 self-alias
  (it's the repo norm).
- **No subqueries against tables or CTEs** — no `in (select ...)`, scalar
  lookups, or correlated subqueries; restructure as a CTE and join it.
  Carve-out: a scalar _aggregate_ over `unnest` of an array
  (`(select min(x) from unnest([...]))`) is row-local and allowed — this is the
  ONLY blessed `unnest` subquery form. An `order by ... limit 1` pick over
  `unnest` is NOT allowed (it violates No `ORDER BY`); for a priority pick over
  a fixed candidate set, use `coalesce(if(cond, a, null), ..., a, ...)`, which
  returns the first non-null in priority order with no subquery.
- **No `ORDER BY`** — ordering belongs in the reporting layer, not dbt models;
  this includes `order by ... limit 1` as a single-row pick inside a scalar
  subquery (express a pick with `coalesce`/`if` or a ranked column filtered by
  `WHERE`). Exempt: macro-generated ordering (`dbt_utils.deduplicate` emits
  `array_agg(... order by ... limit 1)`) and `array(select ... order by ...)`
  element ordering.
- **No `QUALIFY`.** Compute the window function as a named column in a CTE and
  filter it with `WHERE` in the next CTE.
- **No lateral column aliases.** BigQuery rejects a `SELECT`-list alias
  referenced by another item in the same list —
  `select 1 as a, case when a = 1 then 'x' end as b` fails
  `Unrecognized name: a`. It works in Snowflake/DuckDB, so a reviewer may
  propose it to de-duplicate two `CASE`s that share predicates; hoist to a CTE
  or keep the duplication.
- **No `GROUP BY ALL`, and no positional `GROUP BY`** — list grouping columns
  explicitly by name. Both `GROUP BY ALL` and `GROUP BY 1, 2, 3` break silently
  when upstream columns change or the SELECT list is reordered.
- **`DISTINCT` — grain projection only, never dup-masking.** Use `DISTINCT` for
  a `GROUP BY` with no aggregation, and for pure grain projection (every
  projected column is functionally determined by the partition key, so
  byte-identical tuples coalesce). Annotate the latter with the one-line
  `grain projection, not dup-masking` — the annotation is what tells a reviewer
  the `DISTINCT` is deliberate rather than a fan-out mask or a wrong-grain
  source, so it is required. Name the partition key on the same comment when the
  `SELECT` list does not make it obvious. NEVER `SELECT DISTINCT` or
  `qualify row_number() over (...) = 1` to mask upstream duplicates, and never
  `DISTINCT` when a projected column varies within the partition (`min()`,
  `first_value()`) — use `dbt_utils.deduplicate()` (see _Row picking, dedup &
  surrogate keys_) with a `-- TODO:` naming the upstream fix.
- **No one-sided calculations in join predicates.** Any expression computable
  from a single table's columns is precomputed as a named column upstream — `ON`
  matches plain columns. Expressions that inherently combine columns from both
  sides (`st_distance(a.geo, b.geo)`, `st_dwithin(...)`) are allowed — they
  cannot be hoisted. Column-to-column inequality comparisons (half-open
  date-range joins) are comparisons, not calculations.
- **No row-level calculations in `WHERE`.** No functions applied to table
  columns — precompute as a named column. Row-independent expressions on the
  other side of the comparison (`current_date(...)`, `{{ var(...) }}`, literals)
  are fine.
- **`ON` vs `WHERE`** — row filters on the preserved table belong in `WHERE`,
  not `ON`. For `LEFT JOIN`, a filter in `ON` preserves non-matching rows.
  Exception: `FULL JOIN` conditions referencing one side stay in `ON` — moving
  them to `WHERE` collapses the join to an inner.
- **No pass-through "import" CTEs.** Don't open a model with
  `orders as (select * from {{ ref("...") }})` aliases — reference the
  ref/source directly in `FROM`/`JOIN`. Every CTE must do real work (filter,
  derive, aggregate, shape a `dbt_utils.deduplicate` input). Exception: the
  same-name whole-row-STRUCT collision below, which _requires_ reading through a
  `source` CTE. Existing models with import CTEs don't need a sweep — drop them
  opportunistically when editing the model anyway.
- **No `SELECT *` in final `SELECT` of `rpt_`/mart models** — list columns
  explicitly. Get the authoritative column list via
  `INFORMATION_SCHEMA.COLUMNS`:

  ```sql
  select column_name
  from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
  where table_name = '<model_name>'
  order by ordinal_position
  ```

- **Soft-delete filters**: Apply in the **staging model**, not in downstream
  `ON` clauses. Deleted rows should never reach intermediate or mart models.
  Omit columns whose value is predetermined by the WHERE filter (e.g.,
  `deleted_at` after `WHERE deleted_at IS NULL`) — they add no signal.
- **SFTP `source_file_name`**: drop in the staging model with
  `select * except (source_file_name)` — the SFTP IO adds it to every row
  (`core/utils/functions.py`); a contracted `stg_*` that doesn't except it fails
  the contract on the next re-pull after the ingestion change.
- **Google Sheets external-table case**: `select *,` in a staging model inherits
  the sheet header case (often PascalCase). Contract-enforced YAML column names
  must match that case, or use explicit `<raw> as <renamed>` aliasing in the
  staging SQL. Don't rename columns in `sources-external.yml` just to normalize
  case — that rebuilds the external table and forces sheet-header coordination.
- **Least/earliest of N nullable columns**:
  `(select min(x) from unnest([c1, c2, ...]) as x)` — aggregate `min` ignores
  NULLs, unlike `least()` (which returns NULL if any arg is NULL). Avoids the
  nested `coalesce(..., sentinel)` + outer-guard pyramid. sqlfluff CV03 wants a
  trailing comma on the inner `select min(x),`; the `unnest([...])` array
  literal must NOT have one (BigQuery rejects a trailing comma in an array).
- **`dbt_utils.generate_surrogate_key` coerces nulls internally** —
  `cast(null as <type>)` and bare `null` hash identically. Don't add the cast.
- **DATE literal across UNION ALL branches needs explicit cast**: BQ coerces
  `'9999-12-31'` to DATE inside `coalesce(date_col, ...)` but NOT across UNION
  ALL branches when one side is CTE-typed STRING. Use
  `cast('9999-12-31' as date)`. Avoid the `date '9999-12-31'` typed-literal
  form.
- **Pre-compute `lag()` / `format()` inputs in the source CTE** so the
  comparison CTE compares plain columns. Avoids duplicating the expression
  inside `lag(expr)` and the bare-column reference.
- **Timezone-aware today**:

  ```sql
  current_date('{{ var("local_timezone") }}')
  ```

- **sqlfluff ST06 buckets `cast()` as a SIMPLE target**, not a calculation. A
  `cast(...) as x` placed after `date(...)` / `regexp_extract(...)` in the same
  select list fails ST06. Put every `cast()` after the plain column refs and
  before any other function call.
- **BigQuery rejects `\_` in a string literal** (`Illegal escape sequence`).
  Escaping an underscore in a `LIKE` needs `'%\\_focus%'`.
- **sqlfluff ST09 (join order)**: ON-clause predicates list the
  earlier-referenced table on the left, including predicates inside a current
  join that reference a prior-joined table. After
  `from A ... join B ... join C on X`, predicates referencing both `B` and `C`
  write `B.x = C.y`, not `C.y = B.x`.
- **BigQuery-reserved CTE names**: `groups` is reserved (window-frame syntax
  `OVER (... GROUPS BETWEEN ...)`). A CTE named `groups` fails parsing with
  "Expected keyword SELECT but got keyword GROUPS". Use `reporting_groups` or
  similar.
- **`select *` inside UNION ALL CTEs trips CV03**: sqlfluff requires a trailing
  comma after the last column, but `select *` has nothing to trail. Enumerate
  columns explicitly in each UNION branch. Enumerating is also the correctness
  fix, not just the lint fix — BigQuery matches UNION ALL branches by POSITION,
  so two `select *` branches whose column order differs bind the wrong columns
  to each other (a type mismatch fails loudly; two same-typed columns swap
  silently).
- **A standalone `select *` takes a trailing comma** (`select *,`) to satisfy
  sqlfluff CV03 (e.g. `stg_overgrad__schools.sql`; a `source` CTE) — distinct
  from the UNION-ALL case above, which must enumerate columns.
- **A projected column whose name equals its source table binds to the whole-row
  STRUCT, not the column**: a bare `address` ref in
  `from {{ source("focus", "address") }}` resolves to the table range variable
  (dbt's component-backtick `` `proj`.`ds`.`address` `` form), so the model
  silently outputs one struct column and the contract fails listing every field
  as `address.<col>`. Read through a `source` CTE
  (`with source as (select *, from {{ source(...) }})`). A single-backtick MCP
  repro `` `proj.ds.table` `` does NOT reproduce it — use component backticks.
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
- **AL09 on struct subfields**: `value.string_value as string_value` trips AL09
  (alias equals the leaf name). Rename to a distinct alias (`as value_string`)
  rather than dropping it when a downstream PIVOT/ref needs the column named.

## SQL column ordering in SELECT clauses (enforced by ST06)

Columns within a SELECT **must** follow this order — no interleaving:

1. Column enumerations (plain refs), grouped by source table in join order,
   separated by a blank line between each table's group
2. Constants and literals
3. Simple functions (`coalesce(...)`, simple `if(...)`)
4. Nested functions
5. Logicals (`if(condition, true, false)`)
6. Case statements
7. Window functions (`row_number() over (...)`)

When a SELECT reads from a single table/CTE, do not prefix columns with the
alias.

## SQL formatting (sqlfluff-enforced)

All SQL follows `.trunk/config/.sqlfluff` (BigQuery dialect), enforced by CI —
**do not flag code that already follows it.**

## Removing comments changes lint/format behavior

- sqlfmt rejoins statements once a mid-statement comment is gone (`from` /
  `select *,` collapse to one line) — let the pre-commit fmt hook apply it.
- Deleting `{#- ... #}` blocks can newly expose sqlfluff rules (ST06) on
  adjacent code that main passes — sqlfluff skips rules near templated slices.
  If fixing ST06 would reorder a contract/sheet-fixed column list, suppress with
  the repo-standard `trunk-ignore(sqlfluff/ST06)` instead.

## Verifying a comment-only SQL change

Strip `--`, `/* */`, and `{# #}` comments from the old and new blobs, collapse
whitespace, and compare — token identity proves no logic change, and it works
where a dev build cannot (stale personal `zz_` source copies, which
`--favor-state` does not defer). Compiled-SQL identity via `dbt compile` is the
equivalent fallback per model.
