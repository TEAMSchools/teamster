# CLAUDE.md — `dbt/iready/`

Source-system staging project for **i-Ready** (diagnostic and instructional
platform for reading and math). Produces staging and intermediate models.

## Model Structure

```text
models/
  staging/
  intermediate/
  sources-external.yml
```

## Cross-Project Usage

Referenced as a dbt package by `kippnewark` and `kippmiami`; `kipptaf` consumes
the resulting tables via `source()`. The `kippnewark` project uses the
`iready_schema` var (`kippnj_iready`) to point to the correct BigQuery dataset.
The model `stg_iready__instructional_usage_data` is disabled in `kippnewark`.
