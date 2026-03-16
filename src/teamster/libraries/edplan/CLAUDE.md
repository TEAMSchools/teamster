# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Sensor and schema for **EdPlan** (special education / IEP management) SFTP
ingestion. The asset itself is built via `sftp.build_sftp_file_asset()`.

## Files

**`sensors.py`** (`build_edplan_sftp_sensor()`): SFTP sensor that polls the
EdPlan SFTP server for new files and emits a `RunRequest` when a file newer than
the cursor is found. Single-asset sensor (one job per code location).

**`schema.py`**: Avro schemas for EdPlan SFTP file formats.
