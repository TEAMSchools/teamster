# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Thin wrappers around the core SFTP library for **i-Ready** (diagnostic and
instructional platform) SFTP ingestion.

## Files

**`assets.py`** (`build_iready_sftp_asset()`): Wraps `build_sftp_file_asset()`
with i-Ready-specific defaults:

- Remote dir regex: `/exports/{region_subfolder}/(?P<academic_year>\w+)`
- SSH resource key: `ssh_iready`
- Multi-partition: `subject` (ela/math) × `academic_year` (list of fiscal years)
- Slugifies `%` → `percent` in column names

**`sensors.py`** (`build_iready_sftp_sensor()`): SFTP sensor that lists the
i-Ready remote directory, matches files against asset regexes, and emits
`RunRequest`s for new files. Special-cases the current fiscal year directory
(maps to `Current_Year` on the SFTP server).
