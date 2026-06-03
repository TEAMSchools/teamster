# CLAUDE.md — `dbt/renlearn/`

Source-system staging project for **Renaissance Learning** (Accelerated Reader
and STAR assessments). Staging-only project.

## Model Structure

```text
models/
  staging/
  sources-external.yml
```

## Cross-Project Usage

Referenced as a dbt package by `kippnewark` and `kippmiami`; `kipptaf` consumes
the resulting tables via `source()`. The `kippnewark` project uses the
`renlearn_schema` var (`kippnj_renlearn`) to target the correct BigQuery
dataset. Several models (Accelerated Reader, STAR fast/dashboard/skill) are
disabled in `kippnewark`.
