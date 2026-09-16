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
  run launches, re-execution, and run termination. Duplicates on both sides are
  denied in `settings.json` — one tool per job.
- **`terminate_run` here has no `terminate_policy`**, so it can only
  `SAFE_TERMINATE`. A run whose worker is gone will not clear. Fall back to
  `mcp__dagster__free_concurrency_slots` to unblock the pool, and to the
  Dagster+ UI to force-cancel.
- **3 jobs stay on the homebrew server** because this server's tool is a strict
  subset, not because of preference. Identical arguments do NOT mean identical
  payloads — compare the payloads before flipping anything else:
  - `list_runs` — this one has no `tags`, `run_ids`, or time-range filter, and
    `job_name` does not discriminate here because automation-condition runs are
    all `__ASSET_JOB`. It DOES return each run's full `tags`, so filtering
    client-side is possible, but only by paging an unfiltered stream 100 runs at
    a time. It also 500s intermittently on broad filters (`status: "SUCCESS"`,
    `job_name: "__ASSET_JOB"`) and is reliable on narrow ones — retry rather
    than concluding the filter is unsupported.
  - `get_run` — this one returns 9 fields. The homebrew one adds
    `assetSelection`, `stepKeysToExecute`, `parentRunId`, `rootRunId`,
    `stepStats` (per-step status and attempt timings), `updateTime`, and
    `repositoryOrigin`. Its only unique field is `run_config_yaml`, which is
    `{}` in this repo because no asset passes run config. `assetSelection` and
    `stepKeysToExecute` ARE recoverable from the run's log — the
    `ASSET_MATERIALIZATION_PLANNED` events name every selected asset and carry
    `step_key`, and they are at the START of the log (verified: all 24 on page 1
    of a 24-asset run). That is 2 calls for what the homebrew tool answers in 1.
  - `get_run_logs` — no `filter_types`. Events here carry `event_type` and
    `error`, but the order is oldest-first with a 100-event cap, so a step
    failure at the end of a long run is several pages in. Verified: page 1 of a
    100-second failed run covered its first 9 seconds. The alert route is not a
    substitute either — `get_run_alert_notifications` returns empty because this
    deployment has no Dagster+ alert policies configured.
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
- Auth is OAuth per user, so the first call in a fresh Codespace needs `/mcp` →
  authenticate. Header auth (`Dagster-Cloud-Organization: kipptaf` plus a bearer
  token) also works and is the path for a service user.
