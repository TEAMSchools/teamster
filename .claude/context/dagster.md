# Dagster MCP gotchas

## Asset diagnosis

When verifying failures, fetch the most recent run per job (`list_runs` with
`job_name=..., limit=1`, no status filter) — bulk cross-referencing capped
result sets misses retries and recoveries.

Asset keys do NOT include dbt subdirectory layers (`staging/`, `intermediate/`,
or mart `facts`/`dimensions`/`bridges`) —
`kipptaf/people/int_people__location_crosswalk` (not `.../intermediate/...`) and
`kipptaf/marts/fct_x` (not `kipptaf/facts/fct_x`).

`get_asset_condition_evaluations` paginates with
`cursor=<evaluationId of the oldest record returned>` — not a timestamp or
opaque token.

- **The dagster MCP targets a branch deployment via a `deployment` arg.**
  `launch_run`, `launch_multiple_runs`, `get_run`, `get_run_logs`,
  `get_run_compute_logs`, and `terminate_runs` all accept `deployment=<name>`
  (omit for prod). `list_deployments` may return only `prod` — recover a PR's
  branch-deployment name (an opaque hash) from its `deploy` job log line
  `Deploying to branch deployment <hash>` (job id from the
  `dagster-cloud-deploy / deploy` check-run `details_url` `/job/<id>`, then
  `gh api repos/<owner>/<repo>/actions/jobs/<id>/logs`). A dormant branch
  deployment throws `DagsterUserCodeUnreachableError` / `InvalidSubsetError` on
  the first call — retry after ~90s to let the code location warm. BigQuery/GCS
  reads are deployment-agnostic, so downstream data validation via the BigQuery
  MCP works regardless of which deployment wrote the data.
- **Prod dbt models are materialized by `<loc>__automation_condition_sensor`
  runs** (job `__ASSET_JOB`, tag `dagster/from_automation_condition`), NOT dbt
  Cloud (CI-only) or crons. A merged model SQL change goes stale on CODE and is
  rematerialized — including view models (distinct from the data-change
  condition, which skips views) — within minutes of the post-merge location
  deploy. To confirm a rollout landed: `get_location_load_history` (new commit
  LOADED) → `list_runs` / `get_asset_materializations` for the asset.
- **Schedule/sensor-launched runs report `assetSelection: null`** in
  `list_runs`. Read `stepKeysToExecute` and convert `__` → `/` to recover asset
  keys (`kipptaf__tableau__ops_dashboard` → `kipptaf/tableau/ops_dashboard`).
  Cross-check with `get_asset_health` before declaring a backfill complete —
  failure-triage groupings keyed on `assetSelection` silently drop these.
- `mcp__dagster__list_runs` caps at `limit=100` with no truncation signal;
  paginate via `cursor` for incident triage that may exceed 100 runs.
- A running backfill's `get_backfill` `status` can read `REQUESTED` with empty
  `partitionStatusCounts` while its partition runs already execute — use
  `list_runs(tags={"dagster/backfill": "<id>"})` for real per-partition
  progress.
- `mcp__dagster__launch_multiple_runs` requires non-empty `asset_keys` per run —
  jobName alone won't queue. Resolve null-`assetSelection` failures to asset
  keys first.
- `mcp__dagster__launch_run` for a **partitioned** asset takes the partition via
  `tags={"dagster/partition": "<key>"}` — there is no partition arg. The key
  must match the asset's `partitions_def` fmt (e.g. `DailyPartitionsDefinition`
  `%m/%d/%Y` → `05/11/2026`). Preview with `confirm=False` first.
- A run-level **SUCCESS can still carry a FAILED asset check** (e.g.
  `zero_api_errors`) that fired an alert — `list_runs(statuses=["FAILURE"])` and
  day2 step_01 both miss it; check `get_asset_check_executions` (day2 step_16).
  The check payload often lacks the offending entity id — recover it from the
  run's `LogMessageEvent` compute logs (`context.log.info` lines).
- `mcp__dagster__search_assets` `cursor` is the JSON-string form returned by the
  prior call (`"[\"a\",\"b\"]"`), not a bare list.
- **`ASSET_FAILED_TO_MATERIALIZE` on a SUCCESS run is usually benign**: planned
  events are written at run creation from the execution plan (the op cannot
  retract them); the Dagster+ PROD backend — not OSS, not branch deployments —
  reconciles planned-vs-materialized post-run and emits the event for each
  unmaterialized planned asset. For `can_subset` multiassets that yield nothing
  (e.g. dlt idle ticks) they are `failure_type=SKIPPED`, level INFO: no health
  degradation, no alert. Only a real materialization reconciles a planned asset
  — avoid the events by not planning (subset the RunRequest / launch no run),
  never by yielding fake materializations (bumps data versions, fires downstream
  automation). `get_run_logs` hides `materializationFailureType` — confirm
  FAILED-vs-SKIPPED via GraphQL `FailedToMaterializeEvent` fields.
- `get_run_logs` needs the full run UUID (abbreviated ids fail). To find a
  schedule's runs: `list_runs` with `tags={"dagster/schedule_name": "<name>"}`.

## Run failure diagnosis

A step failure's real exception is the **bottom of the error chain**:
`get_run_logs(filter_types=["ExecutionStepFailureEvent"])` →
`error.errorChain[-1].error.message`. The top-level
`DagsterExecutionStepExecutionError` and the day2 collector's
`errorClass`/`errorDetail` only show the wrapper — read the chain bottom before
theorizing about cause (e.g. ADP "Code error" was a transient gateway 404, not
rate-limiting).

Step pod stdout is filtered from `k8s_container` logs. For per-step execution
logs, use Dagster's compute log manager:
`get_run_logs(filter_types=["LogsCapturedEvent"])` →
`get_run_compute_logs(log_key=[run_id, "compute_logs", <logKey>])`. The captured
`context.log.info` output lands in the result's `stderr` field — `stdout` is
`null` for these step pods. `mcp__gke__query_logs` surfaces only run-pod logs.

To map a step Job hash to its actual pod name (random suffix):
`protoPayload.methodName="io.k8s.core.v1.pods.create" protoPayload.resourceName=~"namespaces/dagster-cloud/pods/dagster-step-<hash>"`.

`dagster/max_runtime` clock starts at `STARTED` and includes step-pod scheduling
wait — no `step_execution_timeout` knob exists. When a run hits `max_runtime`
having done little work, suspect step-pod `FailedScheduling`, not slow code or
upstream APIs.

Concurrency-**pool**-blocked runs stay QUEUED, not STARTED (run blocking is the
Dagster >=1.10 default; repo is 1.13), so pool queue-wait does NOT burn
`dagster/max_runtime` (it counts from STARTED). With `k8s_job_executor` (all
locations) each step runs in its own pod (compute is `pid 1`) and a resource's
`setup_for_execution` runs there only after the op's pool slot is claimed — so a
pooled resource's short-lived token/session is not aged by queue-wait. Size a
pooled asset's `max_runtime` for its own run, not for waiting behind siblings.

GKE Autopilot top-of-hour fan-out is the dominant cause of step-pod scheduling
latency. `FailedScheduling` events trace to "Insufficient cpu/memory" (3-9 min
waits) while nodes provision. Image pull is ~2s on cached nodes — don't chase
image slimming.

## Dagster Cloud GraphQL (direct, not via MCP)

Host is `kipptaf.dagster.cloud/<deployment>/graphql` (org is `kipptaf`).
`assetChecksOrError` is nested under `assetNodeOrError`; the evaluation success
field is `success` (not `successful`). `assetMaterializations`
`beforeTimestampMillis` / `afterTimestampMillis` are `String`, not `Float` —
pass quoted numeric strings or the request fails with "type 'Float' used in
position expecting type 'String'".

Claude cannot authenticate direct GraphQL calls — the token comes from `op read`
(hook-blocked). Hand queries to the user to run in the Dagster+ UI GraphQL
playground; the MCP's fixed field selections omit some fields (e.g.
`materializationFailureType` on `FailedToMaterializeEvent`).
