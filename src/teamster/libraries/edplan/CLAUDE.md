# CLAUDE.md — `teamster/libraries/edplan/`

Sensor and schema for **EdPlan** (special education / IEP management) SFTP
ingestion. The asset itself is built via `sftp.build_sftp_file_asset()`.

## Files

**`sensors.py`** (`build_edplan_sftp_sensor()`): SFTP sensor that polls the
EdPlan SFTP server for new files and emits a `RunRequest` when a file newer than
the cursor is found. Takes a list of assets as its `asset_selection`, so it runs
on the implicit asset job and the assets may have different partitions
definitions (Newark's 504 report is unpartitioned). Each run request selects
only the asset whose file matched, with a partition key only when that asset is
partitioned.

**`schema.py`**: Avro schemas for EdPlan SFTP file formats.

**`freshness.py`**: the freshness policy each NJ code location's `freshness.py`
applies to `stg_edplan__njsmart_powerschool`. That model ignores missing
`njsmart_powerschool` partitions, so this policy is what flags a day EdPlan
skipped. Never launch a run for a missing past partition: EdPlan overwrites one
file daily, so the run backdates today's file. Report a materialization for the
gap instead, or leave it.

## Notes

- Backing host `secureftp.easyiep.com` is **GlobalSCAPE EFT 8.1**, advertises
  only `ssh-rsa` host-key algorithms. `SSH_EDPLAN` sets
  `enable_legacy_rsa=True`.
