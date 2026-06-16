# CLAUDE.md — `dbt/deanslist/`

Source-system staging project for **Deanslist** (behavior management, homework
tracking, and student support platform). Produces staging and intermediate
models consumed by district projects and `kipptaf`.

## Model Structure

```text
models/
  staging/     # contract-enforced, one model per Deanslist API endpoint
  intermediate/
```

## Cross-Project Usage

Referenced as a dbt package by `kippnewark`, `kippcamden`, and `kippmiami`;
`kipptaf` consumes the resulting tables via `source()`. Consuming district
projects may disable specific models (e.g., `stg_deanslist__followups`) in their
own `dbt_project.yml`.
