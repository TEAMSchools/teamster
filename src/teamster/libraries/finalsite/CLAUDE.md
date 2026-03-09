# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Two ingestion paths for **Finalsite** (school website/communications platform):

- `api/` — REST API for current contact and enrollment data
- `sftp/` — SFTP file drops for historical/batch data

## `api/`

**`assets.py`** (`build_finalsite_asset()`): Non-partitioned GCS Avro asset.
Calls `finalsite.list(path=asset_name)` to fetch all records.

**`resources.py`** (`FinalsiteResource`): REST client with pagination support.

**`schema.py`**: Avro schemas for Finalsite API responses.

## `sftp/`

**`assets.py`**: Provides `get_finalsite_school_year_partition_keys()` — a
utility that generates `StaticPartitionsDefinition` for school year strings like
`2024_25`. Used by code locations when defining SFTP assets with year-based
partitions. The SFTP asset itself is built via `sftp.build_sftp_file_asset()`.

**`schema.py`**: Avro schemas for Finalsite SFTP file formats.
