# GKE MCP gotchas

Authenticates as impersonated service account
`codespaces@teamster-332318.iam.gserviceaccount.com`. If `PermissionDenied`,
check the `CodespacesRole` custom IAM role, not user IAM bindings.

`gcloud` via Bash is denied by a `Bash(gcloud *)` deny rule (full-path or
variable-aliased invocations are classifier-flagged as evasion — don't). Prefer
the GKE MCP (`list_clusters`/`get_cluster`) and gcp-observability MCP; for
Compute resources with no MCP coverage (Cloud NAT, routers) or the gcloud
commands noted elsewhere in this file, hand them to the user to run.

`mcp__gke__query_logs` uses snake_case keys in `time_range` (`start_time`,
`end_time`), not camelCase. Results cap at 100 — paginate by using the last
entry's timestamp as the next `start_time`. The LQL filter truncates
`time_range` bounds to second precision, so sub-second offsets (e.g.
`...:30.534Z`) are silently rounded down and refetch the same first page. To
page past a sub-second boundary or fetch the tail of a traceback, fall back to
`mcp__gcp-observability__list_log_entries` with `orderBy: "timestamp desc"`.

`query_logs` format templates reject hyphens in dotted key paths
(`{{.labels.k8s-pod/dagster/op}}` fails to parse). Use the Go template `index`
function instead: `{{index .labels "k8s-pod/dagster/op"}}`. Fall back to full
JSON + jq only when nesting is deeper than `index` can express.

For pod-level logs, prefer `mcp__gke__query_logs` over
`mcp__gcp-observability__list_log_entries` — the GKE MCP returns pod labels
(run-id, op, code-location) that the gcp-observability MCP does not.
