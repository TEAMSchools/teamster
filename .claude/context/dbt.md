# dbt Cloud MCP gotchas

Auth via `scripts/dbt-mcp-launch.sh` — do not add `DBT_TOKEN` to `.mcp.json`
directly. Static `DBT_*` and `DISABLE_*` config lives in `.mcp.json`'s `env`
block; only `DBT_TOKEN` is fetched per-launch. `list_jobs` is hard-filtered to
`DBT_PROD_ENV_ID`, currently staging (70403104014899); per-call `environment_id`
/ `project_id` args exposed by the schema are ignored. Run-inspection tools
(`list_jobs_runs`, `get_job_run_details`, `get_job_run_error`) ignore env scope
and work across environments by `job_id` / `run_id`. `list_jobs_runs` for the
shared CI job (`Build - CI (Modified)`) interleaves runs from ALL open PRs with
`git_branch=null` — cross-check a run's `git_sha` against your branch
(`git branch -r --contains <sha>`) before attributing a run or its failure to
your PR. For successful runs, call `get_job_run_error` with `warning_only=true`
to surface test warnings — status=Success does not mean warning-free.

For job inspection, query Staging env (70403104014899) by job id — Production
env (70403104000025) has no scheduled dbt Cloud jobs.

Job config changes must go through the dbt Cloud UI — no mutation tools exist in
the MCP. Live step logs (`debug_logs`, `structured_logs`) and
`list_job_run_artifacts` return nothing until `artifacts_saved: true` — don't
try to diagnose in-flight runs.

`mcp__github__pull_request_read get_status` surfaces dbt Cloud check status
(state + target_url to run page) — fallback when dbt MCP is down.

Remote MCP (`/api/ai/v1/mcp/`) is not available on this account — `team_2022`
plan doesn't expose the `Developer` service-token scope the endpoint requires.
Local MCP only.

## A PR merged mid-CI leaves a permanent `dbt Cloud: failure`

`get_job_run_error` returns `Job run was cancelled` with null step/target, not a
build failure. Rapid sequential merges likewise cancel each prior deploy; only
the tip commit's run survives, which is harmless since it carries every merge.
