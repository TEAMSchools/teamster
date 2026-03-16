# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Integration for **Couchdrop** — an SFTP gateway that mirrors files to Google
Drive. Rather than polling the SFTP server directly, the sensor watches the
corresponding Google Drive folder using `GoogleDriveResource`.

## Files

**`resources.py`** (`CouchdropResource`): REST client for the Couchdrop API
(authenticates, lists files recursively via `ls_r()`). Used for direct file
operations; the sensor uses Google Drive instead.

**`sensors.py`** (`build_couchdrop_sftp_sensor()`): Sensor that:

1. Lists files in a Google Drive folder (the Couchdrop mirror) using
   `google_drive.files_list_recursive()`
2. Matches each file path against each asset's `remote_dir_regex` /
   `remote_file_regex` metadata
3. Emits `RunRequest`s grouped by `(job_name, partition_key)` for new/updated
   files since the cursor timestamp

The sensor handles multi-partition and static-partition assets by extracting
dimension values from regex named groups in the file path.
