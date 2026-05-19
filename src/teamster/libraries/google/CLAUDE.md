# CLAUDE.md — `teamster/libraries/google/`

Google Workspace integrations. Four separate sub-libraries, each with distinct
responsibilities:

## `bigquery/`

Single `ops.py` with a `bigquery_query_op` that runs a BigQuery query and
returns row dicts. Used in extract pipelines.

## `directory/`

Google Admin SDK Directory API integration for user and group management.

**`resources.py`** (`GoogleDirectoryResource`): Authenticates via service
account with domain-wide delegation. Provides batch methods:
`batch_insert_users()`, `batch_update_users()`, `batch_insert_members()`,
`batch_insert_role_assignments()`.

**Retry pattern**: All `.execute()` calls (both `_list` and batch methods) are
wrapped via the module-level `_retryable_execute(request)` factory +
`backoff(fn=..., retry_on=(_TransientHttpError,))`. Never use bare
`errors.HttpError` — 4xx client errors must not be retried. Transient codes:
`{429, 500, 502, 503, 504}`.

**409 conflict handling**: 409 is deliberately excluded from
`_TRANSIENT_HTTP_CODES` because its meaning is method-specific: for
`batch_insert_role_assignments` it means "entity already exists" (not
retryable), but for `batch_update_users` it means "conflicting request, please
try again" (retryable). User update 409s are retried individually via
`_retry_update_user()` after a 1-second cooldown.

**Batch callback signature**: Google's batch executor calls
`callback(id, response, exception)` with exactly one of `response`/`exception`
as `None`. Type both as `X | None`.

**Unit testing**: To mock the API without live credentials, set
`resource._resource = MagicMock()` and target
`mock_resource.<api>.return_value.list.return_value.execute`. Patch
`dagster._utils.backoff.time.sleep` to suppress retry delays in `_list`. To test
batch methods, set `mock_api.new_batch_http_request.side_effect` to a factory
that captures the `callback` kwarg and calls it inside `execute()` — see
`_make_batch_side_effect()` in
`tests/resources/test_resource_google_directory.py`. Patch
`teamster.libraries.google.directory.resources.time.sleep` (not the backoff
path) to suppress inter-batch delays.

**Empty-page responses**: Some API endpoints return `{}` instead of
`{"users": []}` for pages with no items. Use `response.get(key, [])`, not
`response[key]`.

**`schema.py`**: Pydantic models (`User`, `OrgUnits`, `Role`, `RoleAssignment`,
`Group`, `Member`) mirroring the Google Directory API response shapes. Code
locations consume these via `py_avro_schema.generate()` to produce Avro schemas
for IO manager output.

**`ops.py`**: Legacy — use `kipptaf/google/directory/assets.py` instead.

## `drive/`

**`resources.py`** (`GoogleDriveResource`): Wraps the Drive API with a
`files_list_recursive()` helper that traverses folder trees. Used by
`couchdrop/sensors.py` to detect new files dropped in Couchdrop-managed Google
Drive folders.

## `forms/`

**`resources.py`** (`GoogleFormsResource`): Fetches Google Forms responses. Used
to ingest survey data as assets.

## `sheets/`

**`assets.py`** (`build_google_sheets_asset_spec()`): Produces an `AssetSpec`
(not a full asset) from a Google Sheets URL + range. The sheet ID is parsed from
the URL and stored in metadata.

**`sensors.py`** (`build_google_sheets_asset_sensor()`): For each unique sheet
ID, calls `GoogleDriveResource.get_modified_time()` (Drive API
`files.get(fields=modifiedTime)`) and emits `AssetMaterialization` events when
the modifiedTime has advanced past the last cursor value. Uses the
`google_drive` resource key — `gspread` is not used.
