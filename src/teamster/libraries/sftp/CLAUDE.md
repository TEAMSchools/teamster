# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Core factory library for all SFTP-based ingestion assets. Provides three
`build_sftp_*_asset()` functions that produce Dagster assets reading files from
SFTP servers and writing Avro records to GCS via `io_manager_gcs_avro`.

## Factory Functions

| Function                     | Use case                                                   |
| ---------------------------- | ---------------------------------------------------------- |
| `build_sftp_file_asset()`    | Matches a single file (raises if multiple matches)         |
| `build_sftp_archive_asset()` | Downloads a zip archive and extracts one file              |
| `build_sftp_folder_asset()`  | Collects all matching files in a folder, concatenates rows |

All three share the same core parameters:

- `asset_key` — list of strings forming the Dagster asset key
- `remote_dir_regex` — regex for the remote directory path (may contain named
  groups for partition substitution)
- `remote_file_regex` — regex for the filename
- `ssh_resource_key` — name of the `SSHResource` in the resource dict
- `avro_schema` — Fastavro schema for output validation
- `partitions_def` — optional Dagster partitions definition

## Partition Key Substitution

Named groups in `remote_dir_regex` / `remote_file_regex` are replaced with
partition key dimension values via `compose_regex()`. For multi-partition keys,
each dimension name maps to a group name in the regex.

`iready` has special-cased logic: the current fiscal year partition maps to the
`Current_Year` directory on the SFTP server.

## Output

Assets yield `Output(value=(records, avro_schema))` and a schema validity check.
Empty files and zero-row CSVs produce a warning but don't fail. PDFs are parsed
via `pypdf` if `pdf_row_pattern` is provided.
