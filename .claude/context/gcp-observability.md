# GCP Observability MCP gotchas

If any tool returns permission denied, flag it to the user — don't assume no
data. `list_time_series` `alignmentPeriod` must end with `s` (e.g., `"60s"` not
`"60"`). Container metrics (`kubernetes.io/container/*`) are keyed by `pod_name`
— no `node_name` label; use `kubernetes.io/node/*` for node-level data.

`list_log_entries` over a busy day at WARNING+ severity routinely exceeds the
context budget. Pre-filter (`severity`, `resource.type`), cap with `pageSize`,
or dump the result to a file and hand it to a subagent.

Drive and other Workspace APIs (Sheets, Calendar, Gmail) do NOT emit to GCP
Cloud Logging by default — filtering audit logs for
`protoPayload.serviceName="drive.googleapis.com"` returns empty unless Workspace
audit log export is set up separately.

To verify which SA a GKE pod authenticates as, query Cloud Audit logs with
`protoPayload.authenticationInfo.principalEmail="<sa-email>"`.
`iamcredentials.GenerateAccessToken` entries also log the requested OAuth scopes
— disambiguates Workload Identity vs ADC vs SA-file paths.
