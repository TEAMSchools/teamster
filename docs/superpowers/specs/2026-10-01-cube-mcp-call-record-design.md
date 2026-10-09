# Cube MCP call record

Refs [#5613](https://github.com/TEAMSchools/teamster/issues/5613), under
[#5236](https://github.com/TEAMSchools/teamster/issues/5236).

## What this is

We can tell an agent what a Cube measure means. We cannot tell whether it
listened, which questions we fail to answer, or whether a fix helped. This
change records every call our Cube MCP server handles, 1 row per call, in
BigQuery.

It records what the agent was asked, the Cube query it built, and what came
back. It never records the response rows: those are student data.

What we use it for, in priority order:

1. **Refining Cube descriptions, `ai_context` and the MCP tool descriptions** so
   agents query the data correctly. This is the main use.
2. **Pre-aggregation hit rate over time.** Cube Cloud's Query History keeps 24
   hours; this log keeps it permanently. Our 1 pre-aggregation currently serves
   0 queries ([#5557](https://github.com/TEAMSchools/teamster/issues/5557)), and
   nothing told us.

This PR builds the capture only: the server change, the Dagster asset and the
dbt staging model. The analysis built on it is described in
[Deferred](#deferred-to-the-analysis-pr) and ships in a later PR.

## Revision 2026-10-08: engineering review

Bini's
[engineering review](https://github.com/TEAMSchools/teamster/issues/5613#issuecomment-6045255853)
changed the design. Where this section and a later one disagree, this section
wins.

### What changed

1. **Write path: a Cloud Logging sink to BigQuery, not the Dagster pull.**
   [Section 2](#2-dagster-asset) is dropped: no `CloudLoggingResource`, no
   `google-cloud-logging` dependency, no asset, Avro schema or external table,
   and no 30-day loss ceiling.
2. **The free-text switch covers `question` and `assumptions` only, and is off
   by default.** `query_json` and `error_message` always log.
3. **Retention: a partition expiration on the raw table**, not keep-forever.
   People Operations and legal pick the number; 730 days until they do.
4. **Each log line carries `"severity": "INFO"`**, so Cloud Logging never infers
   a severity from the stream and these records never read as errors.
5. **New field `question_provided`** (bool): true when the call passed a
   non-empty `question`. It is PII-free, so the model's fill rate is measurable
   while the switch is off.
6. **2 PRs, not 1.** The sink creates its table on the first routed entry, and
   entries exist only after the server change deploys. PR 1 ships the server,
   tests, deploy workflow and sink guide. PR 2 ships the dbt source and staging
   model once rows exist.

### Free text

| Field           | Logged                                  | Why                                                                                                                                               |
| --------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `question`      | Only with `CUBE_MCP_LOG_FREE_TEXT=true` | Staff can type circumstances that exist nowhere else in the warehouse (a discipline, health or family detail): tier 2 free text in `ferpa-pii.md` |
| `assumptions`   | Only with `CUBE_MCP_LOG_FREE_TEXT=true` | Model-written free text that can repeat what the person typed                                                                                     |
| `query_json`    | Always                                  | Repeats filter values the warehouse already holds. The detectors run on it                                                                        |
| `error_message` | Always                                  | Can echo a filter value back; same reasoning as `query_json`                                                                                      |

All 4 keep `contains_pii: true` in dbt: a `student_number` in a filter is still
a tier-1 identifier.

The `question` and `assumptions` tool parameters stay on the tools while the
switch is off. Turning it on is then a deploy setting with no connector refresh,
and `question_provided` has been measuring compliance the whole time.

- **Deploy**: `.github/workflows/deploy-cube-mcp.yaml` sets
  `CUBE_MCP_LOG_FREE_TEXT=false` explicitly, so turning it on is a 1-line diff
  whose PR carries the People Operations approval. The code default is also
  `false`.
- **Unit test 7** becomes: with the switch unset or `false`, `question` and
  `assumptions` are empty and `query_json` and `error_message` are populated;
  with `true`, all 4 are populated.

### Sink

Setup commands go in a new section of `docs/guides/cube.md`. A person with admin
on both projects runs them once; nothing is in code.

1. Create dataset `cube_mcp_logs` in `teamster-332318` with a default partition
   expiration of 730 days. A dedicated dataset keeps the expiration off every
   other table, and lets access be narrowed later without moving dbt models.
2. Create a sink in `teamster-mcp` with the filter from section 2, destination
   `cube_mcp_logs`, and `--use-partitioned-tables`. The sink writes table
   `run_googleapis_com_stderr`, partitioned by day on `timestamp`.
3. Grant the sink's writer identity `roles/bigquery.dataEditor` on
   `cube_mcp_logs`.

Create the sink before PR 1 deploys. A sink routes only entries written after it
exists, so anything earlier stays in `_Default` and expires in 30 days.

How the sink shapes the table, and what the writer does about it:

- Fields land under a `jsonPayload` record. Each column's type comes from the
  first entry that carries the field, and new fields add columns.
- An entry whose value does not match an existing column's type is not written.
  So the writer keeps each field's JSON type fixed: `null` when absent, never
  `""` where the column holds a number or an array. `query_json` stays a JSON
  string.
- JSON numbers arrive as FLOAT64, because Cloud Logging stores `jsonPayload` as
  a protobuf `Struct`, which has 1 number type. Staging casts `row_count` and
  `latency_ms` to INT64.
- Cloud Run moves `severity` to the entry's own `severity` and strips it from
  `jsonPayload`, so it never becomes a column.
- Check during setup whether `ts` and `last_refresh_time` land as STRING or
  TIMESTAMP. Staging casts both either way.

### dbt (PR 2), replacing section 3's source

- **Source**: `src/dbt/kipptaf/models/cube/sources-bigquery.yml`, source `cube`,
  schema `cube_mcp_logs`, table `run_googleapis_com_stderr`. A plain schema with
  no target prefix, per the BigQuery-native convention, so dev and CI read the
  prod table.
- **Staging**: `stg_cube__mcp_calls` selects from `jsonPayload` and casts every
  column to its final type. Tests and PII tags as in section 3, plus
  `question_provided`.
- **Schedule**: `meta.dagster.automation_condition.cron_schedule: 0 3 * * *`.
  Dagster sees the sink table as an external source that never materializes, so
  the default table condition's upstream-updated trigger never fires and the
  model would build once and go stale.
- **Alarm**: `dbt_utils.recency` on `ts`, day interval 4, `severity: warn`. 4
  days keeps a weekend with no agent traffic quiet; a school break will warn,
  which is acceptable.
- **Expiration flows through.** Staging is a full rebuild, so rows the raw table
  expires leave staging on the next run.

### Open questions after review

Settled: question 4 (sink), question 5 (`_Default` is fine; `teamster-mcp` log
access is no broader than the dataset's), question 6 (existing access is fine).

1. **Retention days** (People Operations and legal). Default 730.
2. **Sign-off on question text** (Walters and People Operations). It now gates
   turning on the switch, not the merge.
3. **Legal classification** of the log. Ask before the switch turns on.
4. **Bini**: confirm `query_json` and `error_message` log unconditionally. The
   review implies it for `query_json` and does not mention `error_message`.

Questions 7 to 9 below are unchanged.

### Deferred work while the switch is off

- **Retry chains** group on `session_id` plus overlapping `members_referenced`
  inside about 5 minutes, instead of similar question text. They detect a
  rephrase but cannot show what the person asked.
- **Error analysis** (reading sessions by hand) and **retiring the Assessment
  Project's session log** both need `question`, so they wait for the sign-off.
- **Detectors, the pre-aggregation hit rate, coverage gaps and unused members**
  need no free text and proceed on the original schedule.

## Open questions for review

Superseded in part: see
[Open questions after review](#open-questions-after-review).

Reviewers: Bini (engineering), Walters and People Operations (privacy and
retention). Each item says what is decided by default if nobody objects.

1. **Retention: rows are kept forever.** That includes `question` text, which
   will name students. Adding a limit later is 1 setting
   (`partition_expiration_days`) on the raw table, but deleted rows cannot come
   back. A 90-day window was discussed and set aside as more mechanism than we
   need now. Default: no expiration.
2. **Sign-off on capturing question text.** The issue made question capture wait
   on Walters and People Operations. Question capture ships switched on, so
   merging this PR is that sign-off. Default: the PR does not merge without
   their approval.
3. **Legal classification of the log.** A stored question that names a student
   is arguably an education record ("directly related to a student" and
   maintained by the network), which parents may ask to inspect under FERPA. NJ
   charter schools likely fall under the Open Public Records Act, and Florida's
   public records law is broad, so a state retention schedule could also require
   keeping or deleting these rows. Default: ask legal before merge; no design
   change unless they say so.
4. **Write path: Dagster pull or Cloud Logging sink (Bini's call).** This spec
   builds the Dagster pull, which matches the repo's pull-to-GCS convention. The
   sink is the alternative with fewer moving parts; see
   [Alternatives](#alternatives-considered). Default: Dagster.
5. **Cloud Logging's own copy.** With the Dagster pull, Cloud Logging is the
   buffer, so every line, question text included, also sits in the
   `teamster-mcp` project's `_Default` log bucket for 30 days under that
   project's access rules. The tighter option is routing these lines to a
   dedicated log bucket with restricted access. Default: `_Default`.
6. **Who can read `kipptaf_cube`.** The new dataset holds `question` and
   `query_json`. Default: the same access as other `kipptaf_*` source datasets.
   Say so if it needs a restricted dataset instead.
7. **Models over logged question text.** Clustering or summarizing questions
   with a model (deferred work) needs legal or People Operations to confirm that
   our agreements cover that use. Running it in Vertex AI inside GCP avoids
   sending text to another provider. Default: nothing runs until confirmed.
8. **Other agent paths into Cube.** The log sees only traffic through our MCP
   server. If anything else calls Cube for an agent, such as Cube Cloud's
   built-in AI assistant, the log misses it. Default: assume none; confirm.
9. **`staff_key` reflects current access, not access at call time.**
   `dim_staff_cube_access` is a current snapshot, so "empty results by
   permission shape" will describe people's permissions today. Default: accept
   for now; fixing it needs snapshots of that dimension.

## Decisions

Settled during design on 2026-10-01. The switch and write-path decisions below
changed in the [2026-10-08 revision](#revision-2026-10-08-engineering-review).

- **Phase 1 and phase 2 of the issue ship together.** Question text and
  `query_json` are captured from the start.
- **A switch, on by default.** `CUBE_MCP_LOG_FREE_TEXT` covers the 4 fields that
  can carry student-identifying text: `question`, `assumptions`, `query_json`
  and `error_message`. Set to `false`, they are logged empty and everything else
  still logs.
- **Build our own record.** Research found no open-source tool that records MCP
  tool calls to a queryable store and fits a PII constraint; see
  [Research](#research).
- **Write path: a JSON log line, pulled daily by Dagster.** See
  [Alternatives](#alternatives-considered) for the sink.
- **Sessions come from the server.** The server mints a `session_id` and the
  model passes it back. The stateless server has no MCP session id of its own.
- **`assumptions` on `load`, no `confidence`.** The model calls `load` before it
  sees results, so a confidence rating there would rate the query, not the
  answer, and models rate themselves poorly in words anyway.
- **All new tool parameters are optional.** Required parameters would break
  every call from a client still holding the old tool list, and invite the model
  to invent values.
- **The Assessment Project's Markdown session log stays** until the rows show
  the model reliably fills in `question`, `session_id` and `assumptions`.

## Design

### 1. Capture in `src/cube/mcp/server.py`

Everything stays in `server.py`: the Dockerfile copies only that file, and the
tests load it by path.

#### New optional tool parameters

| Tool   | New parameters                          |
| ------ | --------------------------------------- |
| `load` | `question`, `session_id`, `assumptions` |
| `sql`  | `question`, `session_id`                |
| `meta` | `session_id`                            |

Each tool description gains 1 short paragraph:

- `question`: pass the person's question verbatim, and the same text on every
  call made for that question.
- `session_id`: if an earlier cube response in this conversation gave you a
  `session_id`, pass it.
- `assumptions`: the interpretive choices you made turning the question into
  this query.

#### 1 wrapper records every call

1. At the start, note the time, create `cube_request_id` (a new UUID), and
   resolve `session_id`. A missing value, or one that is not a valid UUID, gets
   a newly minted id; an invalid value is never logged.
2. `_request()` sends `cube_request_id` as the `x-request-id` header on every
   request in the call, "Continue wait" polls included. Cube stamps it onto the
   BigQuery job as the `cube_request_id` label.
3. After the call, read the response fields: `external`,
   `used_pre_aggregations`, `last_refresh_time`, `row_count`.
4. In a `finally` block, build the row from 1 explicit tuple,
   `CALL_RECORD_FIELDS`, and write it to stderr as 1 JSON line marked
   `"event": "cube_mcp_call"`. Any error while writing is swallowed; the tool's
   own result or exception passes through unchanged.
5. Add a top-level `session_id` to every response. For `meta`, that is a copy of
   the cached catalog; the cached payload is never modified, or every user would
   share 1 id for an hour.

stderr, not stdout: in stdio dev mode, stdout is the MCP transport. In stdio
mode the line shows in the developer's terminal and goes nowhere else.

Each text field is cut at 10,000 characters, which keeps a row far under Cloud
Logging's 256 KB entry limit.

#### Fields

The OTel column names the OpenTelemetry semantic-convention attribute each field
corresponds to, where one exists. Those conventions are in Development status,
so they are recorded in column descriptions, not used as column names.

| Field                   | How the server derives it                                                                                                                                  | Type         | PII | OTel                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | --- | ------------------------------------------------------ |
| `cube_request_id`       | New UUID per tool call                                                                                                                                     | string       | no  | none                                                   |
| `ts`                    | Tool start time, UTC                                                                                                                                       | timestamp    | no  | none                                                   |
| `tool`                  | `meta`, `load` or `sql`                                                                                                                                    | string       | no  | `gen_ai.tool.name`                                     |
| `session_id`            | As passed if a valid UUID, else minted                                                                                                                     | string       | no  | `mcp.session.id`                                       |
| `session_id_minted`     | True when the server minted it on this call                                                                                                                | bool         | no  | none                                                   |
| `email`                 | `_get_user_email()`: the verified OAuth claim                                                                                                              | string       | yes | `user.email`                                           |
| `client`                | `User-Agent` request header                                                                                                                                | string       | no  | `user_agent.original`                                  |
| `question`              | `question` parameter, as passed                                                                                                                            | string       | yes | none                                                   |
| `assumptions`           | `assumptions` parameter, as passed                                                                                                                         | string       | yes | none                                                   |
| `query_json`            | `json.dumps` of the query sent, after the UTC default                                                                                                      | JSON string  | yes | `gen_ai.tool.call.arguments`                           |
| `views_referenced`      | Text before the first `.` of each member; for `meta`, the `views` argument                                                                                 | string array | no  | none                                                   |
| `members_referenced`    | Every member in `measures`, `dimensions`, `segments`, `timeDimensions[].dimension`, `filters[].member` (walking nested `and`/`or`) and `order`; names only | string array | no  | none                                                   |
| `outcome`               | `error` if an exception was raised; `empty` if `load` returned `data: []`; else `ok`                                                                       | string       | no  | `error.type` (partial)                                 |
| `error_message`         | Exception text                                                                                                                                             | string       | yes | none                                                   |
| `external`              | `load` response `external`                                                                                                                                 | bool         | no  | none                                                   |
| `used_pre_aggregations` | `preAggregationId` of each `usedPreAggregations` entry                                                                                                     | string array | no  | none                                                   |
| `last_refresh_time`     | `load` response `lastRefreshTime`                                                                                                                          | timestamp    | no  | none                                                   |
| `row_count`             | `len(data)`; the rows are never logged                                                                                                                     | int          | no  | none                                                   |
| `latency_ms`            | Wall-clock time around the Cube request, polling included                                                                                                  | int          | no  | `mcp.server.operation.duration` (a metric, in seconds) |
| `server_sha`            | `SERVER_SHA` setting, set to `github.sha` at deploy; `local` in stdio                                                                                      | string       | no  | `service.version`                                      |

`external`, `used_pre_aggregations`, `last_refresh_time` and `row_count` are
empty on `meta` and `sql` rows.

Why some of these are built the way they are:

- **Members are extracted in the server**, not in dbt from `query_json`, so the
  PII-free columns stay complete if the switch is turned off.
- **`used_pre_aggregations` stores the pre-aggregation id**, not the table name.
  Table names carry a version hash that changes on every rebuild.
- **`error_message` is PII.** Cube error text can echo a filter value back, and
  filter values can be a `student_number` or a name.
- **`email`, not `staff_key`.** The server cannot reach the warehouse. dbt
  resolves `staff_key` downstream, in the analysis PR.

#### How rows group

- 1 question leads to several calls, typically `meta` then 1 or more `load`
  calls plus retries. Each call is 1 row with its own `cube_request_id`.
- Each call leads to 0 or more BigQuery jobs. 0 is normal when Cube answers from
  its cache or a pre-aggregation.
- A session is 1 conversation: every row sharing a `session_id`. Many minted ids
  from 1 person within minutes means the model is dropping the id, which makes
  compliance measurable from day 1.
- A question is the rows in 1 session with the same `question` text.

Known ways a session can split: a long Claude Code session compacts its context
and loses the id, and Claude Code subagents start without the parent's context.
Both show as a second minted id minutes after the first.

### 2. Dagster asset

Dropped in the [2026-10-08 revision](#sink). The log filter below is reused by
the sink.

Follows the library plus code-location split, modeled on `knowbe4`.

#### Files

- `libraries/google/logging/resources.py`: `CloudLoggingResource`, wrapping
  `google-cloud-logging`'s `list_entries`. New dependency in `pyproject.toml`.
- `libraries/google/logging/assets.py`: a generic
  `build_cloud_logging_asset(code_location, name, project, log_filter, schema)`
  factory, plus the pure entry-to-record mapping function so it can be
  unit-tested without the dbt manifest.
- `libraries/cube/schema.py`: Pydantic `CubeMcpCall`, 1 field per log key, the
  source of the Avro schema.
- `code_locations/kipptaf/cube/`: `assets.py`, `schema.py`, `schedules.py`,
  wired into `definitions.py`.

#### Asset `kipptaf/cube/mcp_calls`

- Daily partitions in `America/New_York`, starting on the deploy date.
- Each partition reads 1 day of entries from project `teamster-mcp`:

  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="cube-mcp"
  jsonPayload.event="cube_mcp_call"
  ```

- Each entry becomes 1 Avro record: the `jsonPayload` fields, plus the entry's
  `insert_id`, `timestamp` and Cloud Run revision name.
- Output through `io_manager_gcs_avro`, with `check_avro_schema_valid`.
- Re-running a partition overwrites its file, so reruns are safe.
- Schedule: daily at 2:00 am Eastern, materializing yesterday's partition.

#### Constraints

- **30-day ceiling.** The `_Default` log bucket keeps entries 30 days. A
  partition not pulled within 30 days is lost, so this asset needs a failure
  alert.
- **IAM.** The Dagster run service account needs `roles/logging.viewer` on
  `teamster-mcp`. A person grants this; it is not in code.

### 3. dbt

The source moved to a BigQuery-native table in the
[2026-10-08 revision](#dbt-pr-2-replacing-section-3s-source).

**Source**: `src/dbt/kipptaf/models/cube/sources-external.yml`

- Source `cube`, dataset `kipptaf_cube`, with the standard dev and staging
  prefix logic.
- Table `src_cube__mcp_calls`: Avro at
  `{cloud_storage_uri_base}/cube/mcp_calls/*`, with `hive_partition_uri_prefix`
  because the asset is daily-partitioned.

**Staging**: `stg_cube__mcp_calls`

- 1 row per tool call, cast to final types: timestamps for `ts` and
  `last_refresh_time`, `query_json` parsed to `JSON`, arrays kept as arrays.
- Contract enforced (inherited). If the server's fields drift, the build fails
  and the previous table stays.
- `unique` and `not_null` on `cube_request_id`, `severity: error`. A failure
  marks the run failed and skips everything downstream; the raw files and the
  external table keep every row.
- `accepted_values` plus `not_null` on `tool` and on `outcome`.
- `contains_pii: true` on `email`, `question`, `assumptions`, `query_json` and
  `error_message`.
- Each column description says how the server derives it and names its OTel
  equivalent.

**Pre-aggregation hit rate** (the phase 1 done-when, as a query, not a model):

```sql
select
    date(ts, 'America/New_York') as call_date,
    count(*) as load_calls,
    countif(external) as served_by_pre_aggregation,
    safe_divide(countif(external), count(*)) as hit_rate,
from kipptaf_cube.stg_cube__mcp_calls
where tool = 'load' and outcome != 'error'
group by call_date
order by call_date
```

The hit rate covers agent traffic only. A pre-aggregation also serves clients
that bypass our server, such as the SQL API, which this log never sees.

### 4. Deploy, tests and checks

**Deploy**: `.github/workflows/deploy-cube-mcp.yaml` adds
`SERVER_SHA=${{ github.sha }}` and `CUBE_MCP_LOG_FREE_TEXT=true` to
`--set-env-vars`. The code also defaults the switch to `true`.

After deploy, claude.ai users must refresh the cube connector before the new
parameters are visible (`src/cube/mcp/CLAUDE.md`, Deploy).

**Unit tests**: `tests/cube/test_mcp_server.py`, Cube mocked

1. Allowlist: for each tool, on the `ok`, `empty` and `error` paths, the logged
   row's keys equal `CALL_RECORD_FIELDS` exactly.
2. No response rows: a `load` returns marker values in `data`, and none appear
   in the logged line.
3. Request id: every request in a call, polls included, sends the same
   `x-request-id`, and it matches the logged `cube_request_id`.
4. Session id: minted when absent; reused when a valid UUID is passed; a
   non-UUID treated as missing and never logged; always returned.
5. Meta cache: 2 calls from different sessions get different ids, and the cached
   payload never holds one.
6. Logging cannot break a call: a failing write still returns the result; a Cube
   error still raises the same exception and logs `outcome = error`.
7. Switch: with `CUBE_MCP_LOG_FREE_TEXT=false`, the 4 free-text fields are
   empty.
8. Member extraction: nested `and`/`or` filters, both `order` forms,
   `timeDimensions`.
9. Limits: text fields cut at 10,000 characters.

**Dagster**: unit tests for the entry-to-record mapping;
`dagster definitions validate` for `kipptaf`; after deploy, a throwaway
credentialed test that pulls 1 real day of entries.

**dbt**: a brand-new Avro external cannot be staged until the asset has written
1 file. Open the PR non-draft, materialize the asset in the branch deployment,
stage with the `gs://teamster-test` override, then build
`stg_cube__mcp_calls --target staging`. After merge, run the prod asset
immediately, or the first scheduled dbt tick fails on an empty prefix.

**Model behavior**: re-run the existing eval on `main` against this branch, to
check the new description paragraphs do not make query building worse. The
harness is unchanged. Fill rates for `question` and `session_id` come from
production rows.

**Checks that need other access**: whether the BigQuery `cube_request_id` label
equals our id exactly, or carries a suffix. That needs `bigquery.jobs.listAll`
on `teamster-332318`. If there is a suffix, the join matches on the prefix.

**Merge order**: #5495 and this PR both edit the `load` and `sql` descriptions
in `server.py` and `tests/cube/test_mcp_server.py`. #5495 merges first; this
branch rebases onto it.

## Privacy

`.claude/rules/ferpa-pii.md` governs this. It applies an existing rule to a new
surface.

- **No response rows**, ever. Enforced by a test.
- **An allowlist in code**, enforced by a test. A change that widens the payload
  fails the build.
- **PII columns are tagged** in dbt: `email`, `question`, `assumptions`,
  `query_json`, `error_message`.
- **`staff_key` is analyzed in aggregate.** Look up an individual only for
  support, and never report a figure per person: the same norm the intake guide
  sets for the Friday number.
- **The eval set stays clean.** The harness never connects to the warehouse, and
  a logged question enters `prompts.yaml` only through a redaction script, never
  by hand. That file is version-controlled and goes to a model provider on every
  eval run.

## Deferred to the analysis PR

Described here so the capture serves them; built later, once #5495's trap checks
are merged and there are weeks of rows.

- **`staff_key` resolution and a sessions model.** Where `staff_key` lives
  (`fct_` in `marts/` or `rpt_`) depends on how the analysis uses it.
- **Detectors.** 1 deterministic check per documented fact, over `query_json`,
  run nightly in dbt. The #5495 traps are the first set. The established name is
  a code-based evaluator; running it on production traffic is online evaluation.
- **Error analysis** (Hamel Husain and Shreya Shankar's evals FAQ). Read 30 to
  50 sessions by hand, label what went wrong, group the labels into a failure
  taxonomy, count each category. Detectors written only from documented facts
  check whether the agent followed the docs and miss failures nobody has written
  down, so new detectors come from the counted taxonomy too.
- **Retry chains.** Same session, similar question text, within about 5 minutes,
  following query reformulation research (Hassan et al., CIKM 2013). Chains
  matching no known detector are the discovery queue.
- **A fortnightly ranked list**: the 10 things most worth fixing in the semantic
  layer, with counts, reviewed in the existing demo-and-retro rhythm.
- **Turning a finding into a fix** reuses the #5495 method: placement sieve,
  per-member draft, check against data, schema test, trap predicate, then an A/B
  eval with the gate written before the results.
- **Clustering questions** with BigQuery embeddings and k-means, pending open
  question 7.
- **A `record_answer` tool** for answer-level confidence, if wanted. Risk:
  models skip an optional extra call.
- **Making `question` required**, once rows show the model fills it reliably and
  users have refreshed their connectors.
- **Retiring the Assessment Project's session log**
  (`src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`), on the
  same evidence.
- **Porting the eval to Inspect AI** when a further eval family is added.

## Alternatives considered

- **Cloud Logging sink to BigQuery.** The same log line; a sink routes matching
  entries into a BigQuery table within seconds. Removes the Dagster asset, the
  Avro files and the external table, and with them the 30-day ceiling. Costs:
  `gcloud` setup outside the repo (commands would go in `docs/guides/cube.md`),
  an inferred `jsonPayload` schema (`query_json` must stay a JSON string), and a
  dbt freshness test as the only alarm. Recommended by the logging research;
  open question 4.
- **Direct BigQuery insert from `server.py`.** Exact schema control, but adds
  `google-cloud-bigquery` to a small image, a cross-project IAM grant, and a
  network write in every call. Rows still being sent are lost on scale-down.
- **Pub/Sub with a BigQuery subscription.** The sink's benefits with more
  infrastructure to own.
- **The MCP SDK's `ServerMiddleware` hook** instead of our own wrapper. It would
  write the row once for all tools, but the SDK labels it provisional for 2.x,
  so a minor `mcp` bump could silently break logging.
- **The SDK's built-in OpenTelemetry middleware.** On by default and inert
  without an exporter. It records neither the tool arguments nor a session id,
  so it cannot be the record.

## Research

Done 2026-10-01. Hard constraint: student PII cannot go to a third-party
service, so a tool qualified only as a library or self-hosted inside our GCP.

- **No off-the-shelf call recorder.** Self-hostable platforms (Langfuse, MLflow
  tracing, Arize Phoenix) add a stateful service holding PII to buy a UI.
  Langfuse's scheduled export to GCS or BigQuery is an Enterprise feature when
  self-hosted; Phoenix is Elastic License 2.0, not open source. MCP gateways add
  a network hop and cannot see Cube fields.
- **Instrumentation packages do not support our SDK.** Traceloop's
  `opentelemetry-instrumentation-mcp` 0.62.4 failed against `mcp` 2.2 when run;
  OpenLIT 1.45.0 wraps classes that no longer exist in 2.x.
- **OpenTelemetry MCP conventions exist in Development status**:
  [semantic-conventions-genai, `mcp.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md).
  Used for the OTel column above.
- **No analysis tool beats dbt SQL here.** The adopted pieces are methods:
  [error analysis](https://hamel.dev/blog/posts/evals-faq/), query reformulation
  as a dissatisfaction signal
  ([Hassan et al., 2013](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/Hassan_CIKM13a.pdf)),
  and in-warehouse embeddings for clustering.
- **Eval tooling.** [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai)
  (MIT) scores tool-call arguments and supports clustered standard errors; the
  port is deferred. A related harness fix (reps pooled into 1 Wilson interval)
  is folded into #5495, not this PR.
