# Dagster+ official MCP gotchas

Dagster's hosted server (`https://mcp.agent.dagster.cloud/mcp`, server name
`Dagster Plus`, Beta). The homebrew `dagster` server stays — neither is a
superset. Gotchas for that one: `.claude/context/dagster.md`.

- **`deployment_name` is a REQUIRED argument on every tool** except
  `list_deployments`. Omitting it returns a pydantic
  `missing_keyword_only_argument` error, not a prod default. Pass
  `deployment_name="prod"`.
- **Mutations have no `confirm` gate.** `launch_job_run`, `launch_asset_run`,
  `rerun_run`, `rerun_backfill`, `terminate_run`,
  `create_or_update_alert_policy`, and `delete_alert_policy` execute on the
  first call. The homebrew server's `confirm=True` preview does not apply here,
  so state the target in plain text before calling one.
- **Prefer this server for any job it covers.** It owns Insights metrics
  (`get_asset_metrics`, `get_job_metrics`, `get_deployment_metrics`,
  `get_asset_selection_metrics` — credit and runtime reporting), alert policies
  (read, plus write via a config document), Dagster+ Issues, asset browsing and
  definitions (`get_assets`, `get_asset`), deployment listing, code locations,
  run listing, run detail, run logs, run launches, re-execution, and run
  termination. The homebrew duplicates are denied in `settings.json` — one tool
  per job.
- **`get_run` here returns 9 fields**, and every field the homebrew one had is
  still reachable:
  - `parentRunId` / `rootRunId` / `repositoryOrigin` → already in this tool's
    own `tags`, as `dagster/parent_run_id`, `dagster/root_run_id` and
    `dagster/code_location`. `dagster/auto_retry_run_id` gives the forward link
    to the retry.
  - `assetSelection` / `stepKeysToExecute` → this server's own `get_run_logs`,
    whose `ASSET_MATERIALIZATION_PLANNED` events are on page 1, one per selected
    asset, each carrying `step_key`.
  - `stepStats` → no direct replacement. This tool's `stats` gives
    `steps_succeeded` / `steps_failed` / `materializations`, and per-step
    timings come from the `STEP_START` / `STEP_SUCCESS` / `STEP_FAILURE` event
    timestamps.
  - `run_config_yaml` is unique to this tool and is `{}` here, because no asset
    in this repo passes run config.
- **`terminate_run` here has no `terminate_policy`**, so it can only
  `SAFE_TERMINATE`. A run whose worker is gone will not clear. Fall back to
  `mcp__dagster__free_concurrency_slots` to unblock the pool, and to the
  Dagster+ UI to force-cancel.
- **`list_runs` here has no `tags`, `run_ids`, or time-range filter.** It does
  return each run's full `tags`, so client-side filtering works over a paged
  stream, but the 2 lookups that needed a server-side tag filter have their own
  routes now:
  - a schedule's or sensor's runs → `mcp__dagster__get_tick_history`, where each
    tick carries its `runIds`.
  - a backfill's progress → `mcp__dagster__get_asset_partition_statuses` on the
    backfilled asset.

  It also **500s intermittently on broad filters** (`status: "SUCCESS"`,
  `job_name: "__ASSET_JOB"` each failed then succeeded on retry) and is reliable
  on narrow ones. Retry rather than concluding the filter is unsupported.
  `job_name` does not discriminate much here anyway, because
  automation-condition runs are all `__ASSET_JOB`.

- **This server owns run logs outright, and the tool overlap is now zero.** The
  homebrew `get_run_logs` was dropped in `dagster-plus-mcp` once the only thing
  it uniquely provided — the compute-log `logKey` — moved inside
  `mcp__dagster__get_run_compute_logs` and
  `mcp__dagster__get_captured_logs_metadata`, which now take `run_id` plus an
  optional `step_key` and resolve the key themselves. Nothing here needs a deny
  for log reading any more.
  - This tool caps `limit` at 100 (passing 1000 is a validation error), has no
    `filter_types`, and returns events oldest-first, so a step failure at the
    end of a long run is several pages in — 4 pages and 329 events on one
    100-second run.
  - Its error payload is `className`, `message`, `stack` and `cause`. Walk
    `error.cause` for the nested parent error.
  - Event types are DagsterEventType names (`STEP_FAILURE`, `LOGS_CAPTURED`,
    `ASSET_MATERIALIZATION_PLANNED`), not GraphQL `__typename` values.
  - **It cannot reach compute logs.** Its `LOGS_CAPTURED` event omits `logKey`,
    that key is an opaque 8-character string not derivable from `run_id` and
    `step_key`, and the files live in Dagster's own S3 bucket. Step-pod
    stdout/stderr comes only from `mcp__dagster__get_run_compute_logs`.

  Identical arguments do NOT mean identical payloads — compare the payloads
  before flipping anything else.

- **The alert route is not a substitute for reading logs.** 13 alert policies
  exist, but none fires on run failure: the run-scoped ones are `JOB_SUCCESS`
  and `JOB_LONG_RUNNING`, and the rest are asset-health, `TICK_FAILURE`,
  `CODE_LOCATION_ERROR` and `AGENT_UNAVAILABLE`. So
  `get_run_alert_notifications` on a failed run returns empty. Revisit if a
  `JOB_FAILURE` policy is ever added.
- `list_code_locations` here drops `updatedTimestamp` and `repositories`, but
  the commit hash is in the `image` tag and
  `mcp__dagster__get_location_load_history` is the rollout-verification tool
  anyway — so this server owns it.
- `list_asset_checks` is the only route to an asset's check NAMES, which
  `mcp__dagster__get_asset_check_executions` requires as `check_name`. Use the
  two together.
- **`health` is 4 current-state enums** — `asset_health`,
  `materialization_status`, `asset_checks_status`, `freshness_status`, each
  `HEALTHY` / `DEGRADED` / `WARNING` / `UNKNOWN` / `NOT_APPLICABLE`, derived
  from each check's and partition's latest execution whenever that ran.
  `get_assets` with a `prefix` returns them for a whole prefix, which is the
  asset health sweep; `get_asset_health` on the homebrew server is denied. The
  enums carry no counts, so drill down from a non-HEALTHY one:
  - `asset_checks_status` → `list_asset_checks` for the check names, then
    `mcp__dagster__get_asset_check_executions` per name for pass/fail. The
    Insights metrics `__dagster_asset_check_errors` /
    `__dagster_asset_check_successes` count outcomes over a time window instead,
    so a check that failed before the window and has not re-run since reads 0
    there while the enum still reads DEGRADED.
  - `materialization_status` → `mcp__dagster__get_asset_partition_statuses` for
    `numMaterialized` / `numPartitions` / `numFailed`. Verified: an asset
    reading `HEALTHY` returned 349 of 450 materialized, so a HEALTHY partitioned
    asset can still be 101 partitions short.
  - `freshness_status` → `get_asset`'s own `latest_materialization_timestamp`.
- **`list_deployments` with `deployment_type="branch"` returns the branch
  deployments**, which the homebrew server's `list_deployments` does not. The
  names are opaque hashes, so mapping a specific PR to its hash still goes
  through that PR's `deploy` job log (see `.claude/context/dagster.md`).
- `get_assets` / `get_asset` return more per asset than `search_assets` did: the
  health rollup, partition definition, job names, downstream keys, and metadata
  entries in one call. They do NOT return staleness causes or
  automation-condition evaluations — those stay on the homebrew server.
- `get_assets` `cursor` is the asset key's JSON-string form (`"[\"a\",\"b\"]"`),
  and `prefix` is a list of key parts (`["kipptaf", "extracts"]`), not a
  slash-separated string.
- Tools return `structuredContent` alongside the text block, unlike the homebrew
  server's raw JSON strings.
- Auth is the same `DAGSTER_CLOUD_API_TOKEN` the homebrew server uses, not
  OAuth, so no `/mcp` authenticate step is needed in a fresh Codespace. The
  `headersHelper` field in `.mcp.json` runs
  `scripts/dagster-plus-mcp-headers.sh` at connection time, which sources
  `scripts/dagster-mcp-launch.sh --no-exec` and prints
  `{"Authorization": "Bearer …", "Dagster-Cloud-Organization": "kipptaf"}`. A
  401 from every tool means that helper failed — run it directly and check it
  emits JSON on stdout and nothing on stderr. Claude Code kills it after 10s; it
  takes about 0.7s.
