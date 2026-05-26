# CLAUDE.md — `teamster/libraries/edplan/`

Sensor and schema for **EdPlan** (special education / IEP management) SFTP
ingestion. The asset itself is built via `sftp.build_sftp_file_asset()`.

## Files

**`sensors.py`** (`build_edplan_sftp_sensor()`): SFTP sensor that polls the
EdPlan SFTP server for new files and emits a `RunRequest` when a file newer than
the cursor is found. Single-asset sensor (one job per code location).

**`schema.py`**: Avro schemas for EdPlan SFTP file formats.

## Notes

- Backing host `secureftp.easyiep.com` is **GlobalSCAPE EFT 8.1**, advertises
  only `ssh-rsa` host-key algorithms. `SSH_EDPLAN` sets
  `enable_legacy_rsa=True`.
