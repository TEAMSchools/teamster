# CLAUDE.md — `teamster/libraries/performance_management/`

Schema-only library — Avro schemas for the internal **Performance Management**
system data (staff observation scores, coaching records). Two assets are built
in the `kipptaf` code location: `observation_details` (SFTP via
`sftp.build_sftp_file_asset()`) and `outlier_detection` (BigQuery-backed ML
clustering asset).
