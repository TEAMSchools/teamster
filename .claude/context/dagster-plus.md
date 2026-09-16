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
- **Reach for this server for the 3 things the homebrew one cannot do**:
  Insights metrics (`get_asset_metrics`, `get_job_metrics`,
  `get_deployment_metrics`, `get_asset_selection_metrics` — credit and runtime
  reporting), alert policies (read, plus write via a config document), and
  Dagster+ Issues.
- `get_assets` / `get_asset` return more per asset than `search_assets` +
  `get_asset_health` combined: the health rollup, partition definition, job
  names, downstream keys, and metadata entries in one call. Prefer it for asset
  overview. It does NOT return staleness causes or automation-condition
  evaluations — those stay on the homebrew server.
- `get_assets` `cursor` is the asset key's JSON-string form (`"[\"a\",\"b\"]"`),
  and `prefix` is a list of key parts (`["kipptaf", "extracts"]`), not a
  slash-separated string.
- Tools return `structuredContent` alongside the text block, unlike the homebrew
  server's raw JSON strings.
- Auth is OAuth per user, so the first call in a fresh Codespace needs `/mcp` →
  authenticate. Header auth (`Dagster-Cloud-Organization: kipptaf` plus a bearer
  token) also works and is the path for a service user.
