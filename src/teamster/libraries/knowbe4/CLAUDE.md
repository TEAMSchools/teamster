# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster assets and resource for **KnowBe4** (security awareness training
platform).

## Factory: `build_knowbe4_asset()`

Simple non-partitioned asset factory. Calls `knowbe4.list(resource, params)` to
fetch all records for an endpoint and writes Avro to GCS.

Asset key: `[code_location, "knowbe4", *resource.split("/")]`

## Resource: `KnowBe4Resource`

Paginated REST client (Bearer token auth) against the KnowBe4 API
(`{server}.api.knowbe4.com`). Handles pagination automatically in `list()`.
