# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

## Model Structure

```text
models/
  dds/
    staging/
  mclass/
    api/
      staging/
    sftp/
      staging/
  sources.yml
```

All staging models have `contract: enforced: true`. Both `dds` and `mclass/api`
can be independently enabled/disabled per school in the consuming project's
`dbt_project.yml`.

## Cross-Project Usage

Referenced by `kippnewark`, `kipppaterson`, and `kipptaf`. School projects
selectively enable only the Amplify products they use — for example,
`kipppaterson` disables both `dds` and `mclass/api`.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
