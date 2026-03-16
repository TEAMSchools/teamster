# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **EdPlan** (special education / IEP management
platform). Produces staging and intermediate models consumed by NJ school
projects and `kipptaf`.

## Model Structure

```text
models/
  staging/     # contract-enforced
  intermediate/
  sources.yml
  sources-archive.yml   # legacy archived sources
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. The model
`stg_edplan__njsmart_powerschool_archive` is disabled in NJ school projects
(enabled only in `kipptaf` if needed).

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
