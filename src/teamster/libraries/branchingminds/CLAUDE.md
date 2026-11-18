# CLAUDE.md — `teamster/libraries/branchingminds/`

Schemas and sensor for the **Branching Minds** (BrM) nightly CSV exports, which
BrM writes to `/exports` on the SFTP server we also send our outbound BrM
extracts to. The assets are built with `sftp.build_sftp_file_asset()`.

- **`sensors.py`** (`build_branchingminds_sftp_sensor()`): one sensor and one
  job for every export. A file's fiscal-year partition comes from its mtime in
  local time, not its content: BrM rolls its export window on July 1, and
  several exports have no school-year column to read. The cursor stores each
  asset's max matched mtime, so one export's late file never hides another's.
- Each fiscal-year partition is overwritten nightly until July 1, then freezes
  as that year's snapshot. The code-location assets set
  `current_partition_only=True`, so a backfill of a past year fails instead of
  overwriting its snapshot with today's file.
