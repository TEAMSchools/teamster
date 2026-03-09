# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Asset factory, sensor, and schema for **Titan K12** (school meals / nutrition
management) SFTP ingestion.

## Files

**`assets.py`**: Wraps `build_sftp_file_asset()` for Titan-specific SFTP
structure.

**`sensors.py`** (`build_titan_sftp_sensor()`): SFTP sensor polling
`sftp.titank12.com` for new files. Handles empty directories gracefully (catches
`SSHException`). Non-partitioned assets only.

**`schema.py`**: Avro schemas for Titan K12 SFTP file formats.
