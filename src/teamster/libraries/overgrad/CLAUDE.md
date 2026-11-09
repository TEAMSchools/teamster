# CLAUDE.md — `teamster/libraries/overgrad/`

Dagster assets and resource for the **Overgrad** college counseling platform.

## Factory: `build_overgrad_asset()`

Produces a GCS Avro asset for a single Overgrad API endpoint. Supports both
paginated list endpoints (no partition) and single-record endpoints (partitioned
by ID).

`students`, `admissions`, and `followings` pull through `list_by_cursor()`, then
`merge_by_id()`. Overgrad sorts list results by `updated_at` ascending and
ignores sort parameters, so page-number paging skips a record whenever another
is edited or deleted mid-pull. Do not move these endpoints back to `list()`.

For `admissions` and `followings` endpoints, post-processes the response to
collect all unique `university.id` values and adds them as a dynamic partition.

Uses a `pool` to rate-limit concurrent API calls per code location
(`overgrad_api_limit_<code_location>`).

## Resource: `OvergradResource`

REST client with `list()` (auto-paginates up to `page_limit`),
`list_by_cursor()` (pages on the last `updated_at` seen; the result repeats
records, so dedupe by `id`), and `get()` (single record by ID). Authenticates
via `ApiKey` header.
