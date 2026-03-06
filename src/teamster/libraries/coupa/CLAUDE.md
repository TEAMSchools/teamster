# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster asset factory and resource for **Coupa** (procurement/spend management
platform).

## Factory: `build_coupa_asset()`

Simple non-partitioned GCS Avro asset. Fetches all records for a Coupa resource
type, normalizes hyphenated keys to underscores (e.g., `account-type` →
`account_type`), and writes Avro to GCS.

## Resource: `CoupaResource`

OAuth2 `BackendApplicationClient` session. Authenticates against the Coupa
instance URL. Provides `list()` with automatic pagination.
