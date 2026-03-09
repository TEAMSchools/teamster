# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster assets and resource for the **Deanslist** behavior management platform.
Assets are school-partitioned (each school has its own Deanslist subdomain and
API key).

## Factory Functions

Three builders cover different endpoint access patterns:

| Function                                            | Partition type                              | Use case                                                               |
| --------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `build_deanslist_static_partition_asset()`          | `StaticPartitionsDefinition` (school IDs)   | Simple per-school endpoints                                            |
| `build_deanslist_multi_partition_asset()`           | `MultiPartitionsDefinition` (school × date) | Date-windowed endpoints using `UpdatedSince` / `StartDate` / `EndDate` |
| `build_deanslist_paginated_multi_partition_asset()` | `MultiPartitionsDefinition`                 | Large paginated endpoints; uses `io_manager_gcs_file` instead of Avro  |

Date windows are computed from `FiscalYear` (July start). For
`MonthlyPartitionsDefinition`, `EndDate` is the last day of the month; for
`FiscalYearPartitionsDefinition`, it's the fiscal year end.

## Resource: `DeansListResource`

Configured with `subdomain` + `api_key_map` (a YAML file mapping school IDs to
API keys). Provides `get()` and `list()` methods.
