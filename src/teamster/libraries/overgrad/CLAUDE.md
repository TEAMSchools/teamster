# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster assets and resource for the **Overgrad** college counseling platform.

## Factory: `build_overgrad_asset()`

Produces a GCS Avro asset for a single Overgrad API endpoint. Supports both
paginated list endpoints (no partition) and single-record endpoints (partitioned
by ID).

For `admissions` and `followings` endpoints, post-processes the response to
collect all unique `university.id` values and adds them as a dynamic partition.

Uses a `pool` to rate-limit concurrent API calls per code location
(`overgrad_api_limit_<code_location>`).

## Resource: `OvergradResource`

REST client with `list()` (auto-paginates up to `page_limit`) and `get()`
(single record by ID) methods. Authenticates via `ApiKey` header.
