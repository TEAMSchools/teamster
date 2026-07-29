# CLAUDE.md — `teamster/libraries/renlearn/`

Sensor (`build_renlearn_sftp_sensor()`) and Avro schemas for **Renaissance
Learning** (STAR/Accelerated Reader) SFTP ingestion. The asset itself is built
via `sftp.build_sftp_file_asset()`. The sensor handles multi-partition assets
(partition keys from regex named groups) and groups run requests by
`(job_name, partition_key)`.
