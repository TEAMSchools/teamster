# BigQuery MCP gotchas

Truncates results at 50 rows. When querying `INFORMATION_SCHEMA.COLUMNS` for
wide tables, paginate with `WHERE ordinal_position > N`.

`<dataset>.__TABLES__` exposes `last_modified_time` and `type` (1=table, 2=view)
— use it to check whether a model rebuilt or is a live view.
`INFORMATION_SCHEMA.TABLES` has neither. `__TABLES__.row_count` lags — it can
read `0` for a table that already holds rows (e.g. just after a CI rebuild);
confirm population with `COUNT(*)`, not `__TABLES__.row_count`.

Verifying a just-re-materialized partition: the external-table query can read
the **stale pre-overwrite file for minutes even with `_FILE_NAME`**
(file-listing lag after `create or replace`) — a re-pull that changed the data
still shows the OLD rows/count. Cross-check the run's materialization
`record_count` + `data_version` via `mcp__dagster__get_asset_materializations`
(ground truth) before concluding a re-pull did or didn't change anything.

Hyphenated identifiers in INFORMATION_SCHEMA paths need backticks — `region-us`
as a bare token fails with "Syntax error: Expected end of input but got '-'".
Write `` `teamster-332318`.`region-us`.INFORMATION_SCHEMA.TABLES ``.

Single quotes inside a BigQuery string literal escape with a **backslash**
(`'O\'odham'`), not by doubling (`''`) — the doubled form fails with
"concatenated string literals must be separated by whitespace".

The BigQuery MCP service account **cannot read GOOGLE_SHEETS external tables**
("Access Denied: ... while getting Drive credentials", 403) — it lacks Drive
scope. To inspect a sheet-backed source's rows, build the staging model via dbt
(`dbt build --select <stg_model> --target staging`; ADC has Drive scope), then
query the materialized `zz_stg_*` table — a native BQ table, not Drive-backed.

`bq` CLI fallback for shell contexts (Monitor poll loops): binary at
`/usr/local/share/google-cloud-sdk/bin/bq`, `--project_id=teamster-332318`. Same
SELECT-only constraints apply. `bq query` with the SQL passed as a positional
arg crashes its flag parser when the query text starts with a `--` comment
("Unknown command line flag ..." / RecursionError) — the `--` end-of-flags
separator does NOT help. Start the query with `WITH`/`SELECT` (strip leading
comment lines). Pass backtick/quote-heavy SQL via `"$(cat file.sql)"` to dodge
shell-quoting. `--max_rows` defaults to 100 — raise it for full dumps. To hand
PII to Ops, redirect to a local `.claude/scratch/*.csv`
(`bq query --format=csv ... > file`; the `>` keeps PII out of the tool result),
verify with `wc -l`, and reference the FILE (never the values) in any tracker.

**`bq` CLI auth expires mid-session** — it uses gcloud USER creds (not the MCP's
SA), so SELECTs that worked early fail later with "Reauthentication failed"
(non-interactive can't `gcloud auth login`). The BQ MCP keeps working but is
SELECT-only, so **DML/DDL (`DELETE`/`CREATE`/`DROP`) must be handed to the
user's terminal**.

**BQ merge/upsert cost**: clustering the target does NOT prune a dynamic-join
`MERGE` / `DELETE ... WHERE EXISTS` (only partitioning + a _static_ predicate
prunes). `--dry_run` reflects partition pruning but NOT clustering pruning —
measure clustering via actual `total_bytes_billed` in
`INFORMATION_SCHEMA.JOBS_BY_PROJECT`.

Pre-merge queries against PR-branch schema use
`dbt_cloud_pr_<job_definition_id>_<pr_num>_<schema>`. `<job_definition_id>` is
the dbt Cloud CI job ID (stable across runs); read from
`mcp__dbt__get_job_run_details(run_id)` step name
`"Create profile from connection BigQuery (override schema to '...')"`. Prod
`<schema>` lacks unmerged renames. The PR-branch marts schema holds only
`state:modified+` models (often just the fact) — for unmodified dimensional
context, join the PR-branch fact to PROD dims (`kipptaf_marts.dim_*`), which are
absent from the PR schema and unchanged anyway.

To prove a refactor behavior-preserving without a local build, compare the
PR-branch build to prod: `count(*)` plus
`count(distinct format("%T|%T", <key cols>))` on
`dbt_cloud_pr_<job>_<pr>_<schema>.<model>` vs the prod schema. Identical counts
are a value-level proof; `--empty` only proves column resolution.

Chained joins through PR-branch marts (mart-view → mart-view → upstream-view)
hit BigQuery's 16-view nesting limit. Query materialized prod tables instead, or
split the query.

Three BQ query-shape failure modes (not interchangeable):

- `exceeds the maximum allowed number of nested views` — chain depth >16.
  Materialize a mid-chain model.
- `Resources exceeded during query execution: Not enough resources for query planning - query is too complex`
  — fan-out width, can fire well below 16. Materialize the fan-out point.
- `Correlated subqueries that reference other tables are not supported` —
  `array(select ... from unnest(<col>) inner join <table> ...)`. View DDL
  succeeds; reads fail. Restructure to a CTE:
  `cross join unnest + standard join + array_agg`.

`INFORMATION_SCHEMA.JOBS.referenced_tables` lists base tables reached via view
expansion, NOT a directly-selected view. To find consumers of a view, filter by
`REGEXP_CONTAINS(query, '<view_name>')`.

For NULL-safe distinct counts on composite keys, use
`count(distinct format("%T|%T", a, b))` — `concat()` returns NULL when any arg
is NULL and silently miscounts violations.

**Cross-district queries**: Always use `teamster-332318.kipptaf_*` datasets for
queries spanning multiple districts — never manually `UNION ALL` across
`kippnewark_*`, `kippcamden_*`, `kippmiami_*`. Extract district from
`_dbt_source_relation` with
`REGEXP_EXTRACT(_dbt_source_relation, r'`(kipp[^`]+\_<source>)`')`.

Slow/timed-out dbt model: in `JOBS_BY_PROJECT`, same `total_bytes_processed` +
N× `total_slot_ms` across runs of the same model = BigQuery straggler/shard
re-execution (transient), NOT slot contention or a code/data change — confirm
via the `timeline` array (`active_units` not starved) and low competing
slot-minutes in the window. A cancelled BQ job ends `state=DONE` with
`error_result.reason="stopped"`; natural completion has `error_result=null`.

Cost triage ("why did BigQuery costs go up"): query
`` `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT `` grouping
`total_bytes_billed` by `date(creation_time, 'America/New_York')` and
`destination_table.table_id` — attributes spend and rebuild counts directly to
dbt models (on-demand ≈ $6.25/TiB billed; filter `statement_type != 'SCRIPT'` to
avoid double-counting parent jobs). Group by `user_email` to split Dagster vs
dbt Cloud CI vs humans.

Per-column population on a wide table (which optional/custom columns actually
carry data) without dynamic SQL: `to_json(t)` the row, unnest its keys,
subscript. `json_value`'s path argument must be CONSTANT so it cannot take the
unnested key — use `j[k]` and compare `to_json_string`, since a JSON null is not
a SQL NULL:

```sql
with rows_json as (select to_json(t) as j from `<dataset>.<table>` as t)
select k, countif(to_json_string(j[k]) not in ('null', '""')) as populated
from rows_json, unnest(json_keys(j, 1)) as k
group by k
```

Extracting a relation name from `JOBS_BY_PROJECT.query` with a regex catches
developer dev-schema jobs (`zz_<user>_<schema>`) alongside prod. Anchor the
pattern on the full backticked path (`` `<project>`.`<schema>`.`<rel>` ``) or
prod and dev failures land in the same result set.
