# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Avro schemas for **Dayforce** (Ceridian HCM) SFTP file drops. This integration
is currently disabled (`+enabled: false` in `kipptaf/dbt_project.yml`). The
asset is built using `sftp.build_sftp_file_asset()` in the code location when
re-enabled.
