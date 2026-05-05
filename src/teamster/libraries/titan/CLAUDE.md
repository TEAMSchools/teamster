# CLAUDE.md — `teamster/libraries/titan/`

Asset factory, sensor, and schema for **Titan K12** (school meals / nutrition
management) SFTP ingestion.

## Files

**`assets.py`**: Wraps `build_sftp_file_asset()` for Titan-specific SFTP
structure.

**`sensors.py`** (`build_titan_sftp_sensor()`): SFTP sensor polling
`sftp.titank12.com` for new files. Handles empty directories gracefully (catches
`SSHException`). Non-partitioned assets only.

**`schema.py`**: Avro schemas for Titan K12 SFTP file formats.

## Freshness Policies

Code locations attach `FreshnessPolicy.cron` to `titan/person_data` and
`stg_titan__person_data` — deadline 11:30pm, 30-minute window (kippcamden,
kippnewark).
