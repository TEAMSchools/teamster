# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster asset factory and resource for **SmartRecruiters** (recruiting/ATS
platform). Assets fetch pre-built reports via the SmartRecruiters Reporting API.

## Factory: `build_smartrecruiters_report_asset()`

Produces a GCS Avro asset. The asset:

1. POSTs to the reporting API to trigger report execution
2. Polls until the report file is ready (status-based loop with retries)
3. Downloads the CSV and parses it with `csv_string_to_records()`

`report_id` is stored in asset metadata and passed to the API.

## Resource: `SmartRecruitersResource`

REST client authenticated via `X-SmartToken` header. Provides `get()`, `post()`,
`put()`, and `delete()` methods.
