# CLAUDE.md — `teamster/libraries/finalsite/`

Two ingestion paths for **Finalsite** (school website/communications platform):

- `api/` — REST API for current contact and enrollment data
- `sftp/` — SFTP file drops for historical/batch data

## `api/`

**`assets.py`** (`build_finalsite_asset()`): Partitioned GCS Avro asset
(`DailyPartitionsDefinition`, `start_date="2026-08-11"`) — derives the API
`since` parameter from the partition key, so each tick pulls only records
changed since the prior partition rather than the full `finalsite.list`
response.

**Concurrency (do NOT parallelize).** All districts' `contacts` schedules fire
at `00:15` and `12:00` ET simultaneously. The Finalsite gateway throttles by
shared egress IP and returns a bare nginx `403` (not `429`) under concurrent
pulls, despite separate subdomains/credentials — so `build_finalsite_asset` puts
every district's op in one shared `finalsite_api` pool (limit **1**, set in
Dagster+ Deployment then Concurrency; the `pool=` kwarg alone does nothing until
the limit is configured). `_request` also retries `403` and transient network
faults. Pagination is sequential cursor-only (~1 req/s, 25/page): a full/seed
pull for kippnewark (~24k contacts) is ~20 min, but an incremental tick is ~81
pages (~1-2 min).

**`resources.py`** (`FinalsiteResource`): REST client with pagination support.

**`schema.py`**: Avro schemas for Finalsite API responses.

## `sftp/`

**`assets.py`**: Provides `get_finalsite_school_year_partition_keys()` — a
utility that generates `StaticPartitionsDefinition` for school year strings like
`2024_25`. Used by code locations when defining SFTP assets with year-based
partitions. The SFTP asset itself is built via `sftp.build_sftp_file_asset()`.

**`schema.py`**: Avro schemas for Finalsite SFTP file formats.
