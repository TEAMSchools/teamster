# CLAUDE.md — `dbt/renlearn/`

Source-system staging project for **Renaissance Learning** (Accelerated Reader
and STAR assessments). Staging-only project.

## Model Structure

```text
models/
  staging/     # contract: enforced: true
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark` and `kipptaf`. The `kippnewark` project uses the
`renlearn_schema` var (`kippnj_renlearn`) to target the correct BigQuery
dataset. Several models (Accelerated Reader, STAR fast/dashboard/skill) are
disabled in `kippnewark`.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
