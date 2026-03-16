# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **i-Ready** (diagnostic and instructional
platform for reading and math). Produces staging and intermediate models.

## Model Structure

```text
models/
  staging/     # contract: enforced: true
  intermediate/
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark` and `kipptaf`. The `kippnewark` project uses the
`iready_schema` var (`kippnj_iready`) to point to the correct BigQuery dataset.
The model `stg_iready__instructional_usage_data` is disabled in `kippnewark`.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
