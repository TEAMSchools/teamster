# CLAUDE.md — `dbt/finalsite/`

Source-system staging project for **Finalsite** (school website and
communications platform). Staging-only project with no intermediate layer.

## Model Structure

```text
models/
  staging/     # materialized: table
  sources-external.yml
```

Uses `cloud_storage_uri_base` and `local_timezone` vars (both `null` here, set
by consuming projects).

## Cross-Project Usage

Referenced as a dbt package by all four district projects (`kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`). `kipptaf` consumes the resulting
tables via `source()`.
