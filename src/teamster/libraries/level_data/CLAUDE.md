# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster asset factory and resource for **LevelData Grow** (formerly SchoolMint
Grow) — the performance management / staff observation platform.

## Factory: `build_grow_asset()`

Produces a GCS Avro asset. Supports multi-partitioned assets (by `archived`
status × `last_modified` date). For multi-partition keys, passes `lastModified`
and `archived` filters to the API.

## Resource: `GrowResource`

OAuth2 `BackendApplicationClient` session against `grow-api.leveldata.com`.
Paginates via `skip`/`limit` params. Default response limit is 100 records per
page.

## Notes

`grow/ops.py` was deleted — the `grow_user_update_op` and
`grow_school_update_op` ops it contained are superseded by the `grow_user_sync`
asset.
