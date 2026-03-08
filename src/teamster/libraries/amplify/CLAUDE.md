# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Two Amplify product integrations with distinct access methods:

- `dibels/` — Amplify DIBELS Data System (DDS) via REST API
- `mclass/api/` — Amplify mClass via REST API ("Download Your Data" reports)
- `mclass/sftp/` — Amplify mClass via SFTP (sensor only)

## `dibels/`

**`assets.py`** (`build_amplify_dds_report_asset()`): Calls the DIBELS Data
System API to download district-wide reports. Parses CSV responses with pandas.
Assets are multi-partitioned (by school year + benchmark period).

**`resources.py`** (`DibelsDataSystemResource`): OAuth2 session against the
Amplify DDS API endpoint.

**`schedules.py`**: Schedule builder for DDS report assets.

## `mclass/api/`

**`assets.py`** (`build_mclass_asset()`): Calls the mClass "Download Your Data"
(DYD) endpoint, which accepts a payload specifying the report type and school
year. Returns CSV; stored as Avro.

**`resources.py`** (`MClassResource`): Session-based REST client for the mClass
API.

## `mclass/sftp/`

**`sensors.py`** (`build_amplify_mclass_sftp_sensor()`): SFTP sensor that
detects new mClass files using `SSHResource.listdir_attr_r()`, matching paths
against asset `remote_dir_regex`/`remote_file_regex` metadata. Extracts
partition keys from regex named groups.
