# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

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

**`ops.py`**: Four ops for user/member/role provisioning:
`google_directory_user_create_op`, `google_directory_user_update_op`,
`google_directory_member_create_op`,
`google_directory_role_assignment_create_op`. These are used in provisioning
pipelines (not standalone assets).

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

**`sensors.py`** (`build_google_sheets_asset_sensor()`): Polls
`spreadsheet.get_lastUpdateTime()` for each unique sheet ID, emits
`AssetMaterialization` events when a sheet has been updated since the last
cursor timestamp.
