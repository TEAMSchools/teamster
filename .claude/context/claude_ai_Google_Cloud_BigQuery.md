# BigQuery gotchas

## Which client

Three identities reach BigQuery here, and they differ in what they can read:

- **MCP** (`mcp__claude_ai_Google_Cloud_BigQuery__*`) — Google's hosted server
  (`https://bigquery.googleapis.com/mcp`) through the claude.ai connector. It
  runs as the signed-in USER over OAuth with the `bigquery` scope only, so it
  reads everything that user can, PII included. Default for warehouse
  inspection. Cannot read GOOGLE_SHEETS external tables.
- **ADC from Python** — carries Drive scope and does not expire. The only client
  that reads a sheet-backed external live.
- **`bq` CLI** — gcloud USER creds that expire mid-session: SELECTs that worked
  early fail later with "Reauthentication failed" or "You do not currently have
  an active account selected" (non-interactive can't `gcloud auth login`); both
  mean expiry, not a missing grant. Switch to the MCP or ADC rather than
  retrying. For shell contexts (Monitor poll loops) and CSV dumps only.

## MCP tools

- `execute_sql_readonly` for every query. `execute_sql` (read-write) is in
  `permissions.deny`. The read-only tool is enforced by Google's server, not a
  local hook: a non-SELECT fails with
  `MCP execute_sql_readonly tool allows only SELECT statements.` before BigQuery
  resolves any table (verified 2026-09-25 with an `INSERT` into a nonexistent
  table). Warehouse DML/DDL still goes to the user's terminal.
- **Results are capped at 3,000 rows, silently.** A 3,500-row query returned
  exactly 3,000 rows with no `totalRows`, `pageToken`, or marker (verified
  2026-09-25). Never read a 3,000-row result as complete: page on with
  `get_query_results` passing the returned `jobId`, `location: "US"`, and
  `startIndex: "3000"`.
- A query past the ~20s synchronous wait returns `jobComplete: false` with a
  `jobId`. Poll `get_query_results` until `jobComplete: true`, or `cancel_job`.
  Google's docs cap a query at three minutes.
- Rows come back in the raw REST shape, `rows[].f[].v`, every value a string,
  and a TIMESTAMP as epoch seconds in float notation (`1.79034505368E9`). Format
  in SQL (`format_timestamp('%F %R', ts)`) when a human reads the result.
- Jobs carry the label `goog-mcp-server: true`, and `user_email` is the user's,
  not a service account's. Filter on that label to separate Claude's queries
  from the user's own in `JOBS_BY_PROJECT`.

The MCP cannot read GOOGLE_SHEETS external tables:
`Access Denied: BigQuery BigQuery: Permission denied while getting Drive credentials`
(verified 2026-09-25 against
`kipptaf_google_sheets.src_google_sheets__state_test_comparison_demographics`).
Its OAuth token carries the `bigquery` scope only, and sharing the file does not
change that. ADC does have Drive scope, so query the external directly from a
Python client instead — no dbt build, no `stage_external_sources`, and it reads
the sheet live, so a paste is verifiable seconds after it happens. Run the
script with `uv run python <script.py>`:

```python
from google.cloud import bigquery

client = bigquery.Client(project="teamster-332318")
rows = client.query("select ... from `teamster-332318`.<dataset>.<src_table>")
```

Build into a dev/staging table only when something downstream must read it, not
to look at rows.

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

## Metadata and staleness

`<dataset>.__TABLES__` exposes `last_modified_time` and `type` (1=table, 2=view)
— use it to check whether a model rebuilt or is a live view.
`INFORMATION_SCHEMA.TABLES` has neither. `__TABLES__.row_count` lags — it can
read `0` for a table that already holds rows (e.g. just after a CI rebuild);
confirm population with `COUNT(*)`, not `__TABLES__.row_count`.

Verifying a just-re-materialized partition: the external-table query can read
the stale pre-overwrite file for minutes even with `_FILE_NAME` (file-listing
lag after `create or replace`) — a re-pull that changed the data still shows the
OLD rows/count. Cross-check the run's materialization `record_count` +
`data_version` via `mcp__dagster__get_asset_materializations` (ground truth)
before concluding a re-pull did or didn't change anything.

`INFORMATION_SCHEMA.JOBS.referenced_tables` lists base tables reached via view
expansion, NOT a directly-selected view. To find consumers of a view, filter by
`REGEXP_CONTAINS(query, '<view_name>')`.

Extracting a relation name from `JOBS_BY_PROJECT.query` with a regex catches
developer dev-schema jobs (`zz_<user>_<schema>`) alongside prod. Anchor the
pattern on the full backticked path (`` `<project>`.`<schema>`.`<rel>` ``) or
prod and dev failures land in the same result set.

## Query shapes that fail

Three failure modes, not interchangeable:

- `exceeds the maximum allowed number of nested views` — chain depth >16.
  Materialize a mid-chain model. Chained joins through PR-branch marts
  (mart-view → mart-view → upstream-view) hit this; query materialized prod
  tables instead, or split the query.
- `Resources exceeded during query execution: Not enough resources for query planning - query is too complex`
  — fan-out width, can fire well below 16. Materialize the fan-out point.
- `Correlated subqueries that reference other tables are not supported` —
  `array(select ... from unnest(<col>) inner join <table> ...)`. View DDL
  succeeds; reads fail. Restructure to a CTE:
  `cross join unnest + standard join + array_agg`.

## SQL idioms and syntax traps

Hyphenated identifiers in INFORMATION_SCHEMA paths need backticks — `region-us`
as a bare token fails with "Syntax error: Expected end of input but got '-'".
Write `` `teamster-332318`.`region-us`.INFORMATION_SCHEMA.TABLES ``.

Single quotes inside a BigQuery string literal escape with a backslash
(`'O\'odham'`), not by doubling (`''`) — the doubled form fails with
"concatenated string literals must be separated by whitespace".

For NULL-safe distinct counts on composite keys, use
`count(distinct format("%T|%T", a, b))` — `concat()` returns NULL when any arg
is NULL and silently miscounts violations.

Cross-district queries: always use `teamster-332318.kipptaf_*` datasets for
queries spanning multiple districts — never manually `UNION ALL` across
`kippnewark_*`, `kippcamden_*`, `kippmiami_*`. Extract district from
`_dbt_source_relation` with
`REGEXP_EXTRACT(_dbt_source_relation, r'`(kipp[^`]+\_<source>)`')`.

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

## PR-branch and CI schemas

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

## Cost and performance

Merge/upsert cost: clustering the target does NOT prune a dynamic-join `MERGE` /
`DELETE ... WHERE EXISTS` (only partitioning + a _static_ predicate prunes).
`--dry_run` reflects partition pruning but NOT clustering pruning — measure
clustering via actual `total_bytes_billed` in
`INFORMATION_SCHEMA.JOBS_BY_PROJECT`.

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
dbt Cloud CI vs humans, and by the `goog-mcp-server` label to split Claude's MCP
queries out of a human's.
