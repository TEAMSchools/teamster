# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Sensor and schema for **Renaissance Learning** (STAR/Accelerated Reader) SFTP
ingestion. The asset itself is built via `sftp.build_sftp_file_asset()`.

## Files

**`sensors.py`** (`build_renlearn_sftp_sensor()`): SFTP sensor that lists the
Renaissance Learning server for new files matching asset regexes. Handles
multi-partition assets (partition keys extracted from regex named groups),
groups run requests by `(job_name, partition_key)`.

**`schema.py`**: Avro schemas for Renaissance Learning SFTP file formats (STAR
assessments, Accelerated Reader).
